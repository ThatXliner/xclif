"""Build an xclif CLI from an OpenAPI/Swagger spec."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from xclif.command import Command
from xclif.definition import Argument, _DefinitionOption
from xclif.errors import UsageError


def load_spec(source: str | Path) -> dict:
    """Load an OpenAPI spec from a local JSON file or HTTP(S) URL.

    Args:
        source: File path or URL to a JSON OpenAPI spec.

    Returns:
        The parsed spec as a dict.

    Raises:
        UsageError: If the spec cannot be loaded or parsed.
    """
    source_str = str(source)
    if source_str.startswith(("http://", "https://")):
        try:
            response = urllib.request.urlopen(source_str, timeout=30)
            raw = response.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as exc:
            raise UsageError(f"Failed to fetch spec from {source_str!r}: {exc}") from exc
    else:
        path = Path(source)
        if not path.is_file():
            raise UsageError(f"Spec file not found: {source_str!r}")
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise UsageError(f"Failed to read spec file {source_str!r}: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"Invalid JSON in spec {source_str!r}: {exc}") from exc


def _to_snake_case(name: str) -> str:
    """Convert a string to snake_case.

    Handles camelCase (``listPets`` → ``list_pets``),
    PascalCase (``ListPets`` → ``list_pets``),
    kebab-case (``list-pets`` → ``list_pets``),
    and mixed formats (``APIKey`` → ``api_key``).
    """
    s = re.sub(r"[-\s]", "_", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = s.lower().strip("_")
    return s or "unnamed"


def _openapi_type_to_python(schema: dict | None) -> tuple[type, list[str] | None]:
    """Map an OpenAPI schema object to a Python type and optional choices.

    Returns:
        A ``(python_type, choices_or_None)`` tuple.
    """
    if schema is None:
        return str, None

    enum_values = schema.get("enum")
    openapi_type = schema.get("type", "string")

    type_map: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }
    python_type = type_map.get(openapi_type, str)

    choices: list[str] | None = None
    if enum_values:
        choices = [str(v) for v in enum_values]

    return python_type, choices


def _make_run_function(
    url_template: str,
    http_method: str,
    path_param_names: list[str],
    query_param_names: list[str],
    body_param_name: str | None,
) -> Callable[..., int]:
    """Create a run function that makes an HTTP request when invoked."""

    def run_fn(*args: Any, **kwargs: Any) -> int:
        from xclif.context import get_context

        ctx = get_context()
        base_url = str(ctx.get("base_url", "") or "")
        api_key = ctx.get("api_key")
        api_key_header = str(ctx.get("api_key_header", "Authorization"))
        timeout = int(ctx.get("timeout", 30))  # type: ignore[arg-type]
        insecure = bool(ctx.get("insecure", False))  # type: ignore[arg-type]
        raw_output = bool(ctx.get("raw", False))  # type: ignore[arg-type]

        # Build the URL
        url = base_url.rstrip("/") + "/" + url_template.lstrip("/")
        for param_name, arg in zip(path_param_names, args):
            encoded = urllib.parse.quote(str(arg), safe="")
            url = url.replace(f"{{{param_name}}}", encoded)

        # Build query string
        query_parts: list[str] = []
        for param in query_param_names:
            if param in kwargs:
                val = kwargs[param]
                if val is not None:
                    query_parts.append(
                        f"{urllib.parse.quote(param)}={urllib.parse.quote(str(val))}"
                    )
        if query_parts:
            url += "?" + "&".join(query_parts)

        # Build headers
        headers: dict[str, str] = {}
        if api_key:
            headers[api_key_header] = str(api_key)

        # Build request body
        data: bytes | None = None
        if body_param_name and body_param_name in kwargs:
            body_value = kwargs[body_param_name]
            if body_value:
                data = json.dumps(body_value).encode("utf-8")
            else:
                data = b""
            headers.setdefault("Content-Type", "application/json")
        elif body_param_name and http_method in ("POST", "PUT", "PATCH"):
            data = b""
            headers.setdefault("Content-Type", "application/json")

        # Make the HTTP request
        req = urllib.request.Request(
            url, data=data, headers=headers, method=http_method.upper()
        )

        try:
            import ssl

            ssl_ctx = ssl.create_default_context()
            if insecure:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            response = urllib.request.urlopen(
                req, timeout=timeout, context=ssl_ctx
            )

            body = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")

            if "json" in content_type and not raw_output:
                try:
                    parsed = json.loads(body)
                    body = json.dumps(parsed, indent=2)
                except (json.JSONDecodeError, ValueError):
                    pass

            print(body)
            return 0

        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            print(f"HTTP {exc.code} {exc.reason}", file=sys.stderr)
            if err_body:
                try:
                    parsed = json.loads(err_body)
                    err_body = json.dumps(parsed, indent=2)
                except (json.JSONDecodeError, ValueError):
                    pass
                print(err_body, file=sys.stderr)
            return exc.code // 100  # 4xx → 4, 5xx → 5

        except urllib.error.URLError as exc:
            print(f"Error: {exc.reason}", file=sys.stderr)
            return 1

    return run_fn


def _collect_path_params(path: str) -> list[str]:
    """Extract path parameter names from an OpenAPI path template.

    Example: ``/pets/{petId}`` → ``["petId"]``
    """
    return re.findall(r"\{(\w+)}", path)


def _collect_operation_params(
    operation: dict,
) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    """Extract path and query parameter info from an operation.

    Returns:
        ``(path_params, query_params)`` where each entry is ``(name, param_obj)``.
    """
    path_params: list[tuple[str, dict]] = []
    query_params: list[tuple[str, dict]] = []
    for param in operation.get("parameters", []):
        name = param.get("name", "")
        if param.get("in") == "path":
            path_params.append((name, param))
        elif param.get("in") == "query":
            query_params.append((name, param))
    return path_params, query_params


def _has_request_body(operation: dict) -> str | None:
    """Check if an operation has a JSON request body.

    Returns the parameter name to use (``"data"``) or ``None``.
    """
    request_body = operation.get("requestBody")
    if request_body is None:
        return None
    content = request_body.get("content", {})
    # Support application/json and application/*+json
    for media_type in content:
        if "json" in media_type:
            return "data"
    return None


def _operation_command_name(
    operation: dict, method: str, parent_group: str | None
) -> str:
    """Determine the leaf command name for an operation.

    Priority:
    1. ``operationId`` → snake_case
    2. ``summary`` → snake_case
    3. ``method`` (e.g. ``"get"``)
    """
    operation_id = operation.get("operationId")
    if operation_id:
        name = _to_snake_case(operation_id)
        if name:
            return name

    summary = operation.get("summary")
    if summary:
        name = _to_snake_case(summary.split()[0] if summary else "")
        if name:
            return name

    return method


def _static_segments(path: str) -> list[str]:
    """Extract non-parameter path segments from a path.

    Example: ``/pets/{petId}`` → ``["pets"]``
    """
    return [s for s in path.split("/") if s and not re.match(r"\{(\w+)}", s)]


def _build_command_tree(spec: dict) -> Command:
    """Build a complete :class:`~xclif.command.Command` tree from an OpenAPI spec.

    The returned root command can be passed directly to ``Cli(root_command=...)``
    or used with ``Cli.from_swagger()``.
    """
    info = spec.get("info", {})
    title = info.get("title", "api")
    root_name = title.lower().replace(" ", "-").replace("_", "-")

    def _root_help() -> int:
        """Swagger-generated CLI. Use subcommands to interact with the API."""
        return 0

    root_description = info.get("description", "")
    if root_description:
        _root_help.__doc__ = root_description

    root = Command(root_name, _root_help)

    paths = spec.get("paths", {})
    raw_methods = frozenset({"get", "post", "put", "delete", "patch", "head", "options"})

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method in raw_methods:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue

            # Collect parameters
            url_path_params = _collect_path_params(path)
            op_path_params, op_query_params = _collect_operation_params(operation)
            body_param = _has_request_body(operation)

            # All path parameter names (order from path template, then operation declaration)
            all_path_param_names: list[str] = []
            seen_path: set[str] = set()
            for p in url_path_params:
                all_path_param_names.append(p)
                seen_path.add(p)
            for name, _param in op_path_params:
                if name not in seen_path:
                    all_path_param_names.append(name)
                    seen_path.add(name)

            # Query parameter names
            query_param_names = [n for n, _ in op_query_params]

            # Build the leaf command
            static_segs = _static_segments(path)
            parent_group = static_segs[-1] if static_segs else None
            cmd_name = _operation_command_name(operation, method, parent_group)

            run_fn = _make_run_function(
                path,
                method,
                all_path_param_names,
                query_param_names,
                body_param,
            )

            # Set the run function's doc from the operation summary/description
            operation_summary = operation.get("summary", "")
            operation_description = operation.get("description", "")
            if operation_summary:
                run_fn.__doc__ = operation_summary
            elif operation_description:
                run_fn.__doc__ = operation_description

            # Build arguments (path params → positional args)
            arguments: list[Argument] = []
            for name, param in op_path_params:
                schema = param.get("schema", {})
                py_type, choices = _openapi_type_to_python(schema)
                description = param.get("description", "")
                arguments.append(Argument(name, py_type, description, choices=choices))
            # Add any path params not declared in the operation's parameters list
            for name in all_path_param_names:
                if name not in {a.name for a in arguments}:
                    arguments.append(Argument(name, str, ""))

            # Build options (query params → CLI options)
            options: dict[str, _DefinitionOption] = {}
            for name, param in op_query_params:
                schema = param.get("schema", {})
                py_type, choices = _openapi_type_to_python(schema)
                description = param.get("description", "")
                required = param.get("required", False)
                default: Any = None if required else None
                options[name] = _DefinitionOption(
                    name,
                    py_type,
                    description,
                    default=default,
                    choices=choices,
                )

            # Add --data option if there's a request body
            if body_param:
                options[body_param] = _DefinitionOption(
                    body_param,
                    str,
                    "Request body (JSON string)",
                )

            leaf = Command(cmd_name, run_fn, arguments, options)

            # Register the leaf into the command tree hierarchy
            # Static path segments become group commands
            cursor = root
            for segment in static_segs:
                if segment not in cursor.subcommands:
                    cursor.subcommands[segment] = Command(segment, lambda: 0)
                cursor = cursor.subcommands[segment]

            # Handle naming collisions: append method if leaf name already taken
            final_name = cmd_name
            if final_name in cursor.subcommands:
                final_name = f"{method}-{cmd_name}" if method != cmd_name else f"{method}-{len(cursor.subcommands)}"
            cursor.subcommands[final_name] = leaf
            if final_name != cmd_name:
                leaf.name = final_name

    return root
