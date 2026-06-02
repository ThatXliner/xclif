"""Tests for ``xclif.from_openapi``."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from xclif.command import Command
from xclif.errors import UsageError
from xclif.from_openapi import (
    _build_command_tree,
    _collect_path_params,
    _has_request_body,
    _make_run_function,
    _openapi_type_to_python,
    _operation_command_name,
    _static_segments,
    _to_snake_case,
    load_spec,
)

SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Pet Store",
        "description": "A sample pet store API",
        "version": "1.0.0",
    },
    "servers": [{"url": "https://petstore.example.com/api/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Max results",
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "species",
                        "in": "query",
                        "description": "Filter by species",
                        "schema": {"type": "string"},
                    },
                ],
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "species": {"type": "string"},
                                },
                            }
                        }
                    }
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPetById",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "description": "The pet ID",
                        "schema": {"type": "string"},
                    }
                ],
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "description": "The pet ID",
                        "schema": {"type": "string"},
                    }
                ],
            },
        },
    },
}


# ---- _to_snake_case ----


class TestToSnakeCase:
    def test_camel_case(self) -> None:
        assert _to_snake_case("listPets") == "list_pets"

    def test_pascal_case(self) -> None:
        assert _to_snake_case("ListPets") == "list_pets"

    def test_kebab_case(self) -> None:
        assert _to_snake_case("list-pets") == "list_pets"

    def test_mixed_case(self) -> None:
        assert _to_snake_case("APIKey") == "api_key"

    def test_acronyms(self) -> None:
        assert _to_snake_case("getPetById") == "get_pet_by_id"

    def test_spaces(self) -> None:
        assert _to_snake_case("list pets") == "list_pets"

    def test_empty(self) -> None:
        assert _to_snake_case("") == "unnamed"


# ---- _openapi_type_to_python ----


class TestOpenApiTypeToPython:
    def test_string(self) -> None:
        assert _openapi_type_to_python({"type": "string"}) == (str, None)

    def test_integer(self) -> None:
        assert _openapi_type_to_python({"type": "integer"}) == (int, None)

    def test_number(self) -> None:
        assert _openapi_type_to_python({"type": "number"}) == (float, None)

    def test_boolean(self) -> None:
        assert _openapi_type_to_python({"type": "boolean"}) == (bool, None)

    def test_default(self) -> None:
        assert _openapi_type_to_python({"type": "unknown"}) == (str, None)

    def test_none_schema(self) -> None:
        assert _openapi_type_to_python(None) == (str, None)

    def test_with_enum(self) -> None:
        py_type, choices = _openapi_type_to_python(
            {"type": "string", "enum": ["cat", "dog", "fish"]}
        )
        assert py_type is str
        assert choices == ["cat", "dog", "fish"]


# ---- _collect_path_params ----


class TestCollectPathParams:
    def test_no_params(self) -> None:
        assert _collect_path_params("/pets") == []

    def test_one_param(self) -> None:
        assert _collect_path_params("/pets/{petId}") == ["petId"]

    def test_multiple_params(self) -> None:
        assert _collect_path_params("/users/{userId}/pets/{petId}") == [
            "userId",
            "petId",
        ]


# ---- _has_request_body ----


class TestHasRequestBody:
    def test_no_body(self) -> None:
        assert _has_request_body({}) is None

    def test_json_body(self) -> None:
        op = {
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {"type": "object", "properties": {"name": {"type": "string"}}}
                    }
                }
            }
        }
        assert _has_request_body(op) == "data"

    def test_with_wildcard_json(self) -> None:
        op = {
            "requestBody": {
                "content": {
                    "application/*+json": {
                        "schema": {"type": "object"}
                    }
                }
            }
        }
        assert _has_request_body(op) == "data"

    def test_non_json_body(self) -> None:
        op = {
            "requestBody": {
                "content": {
                    "text/plain": {
                        "schema": {"type": "string"}
                    }
                }
            }
        }
        assert _has_request_body(op) is None


# ---- _operation_command_name ----


class TestOperationCommandName:
    def test_from_operation_id(self) -> None:
        name = _operation_command_name(
            {"operationId": "listPets", "summary": "List all pets"},
            "get",
            "pets",
        )
        assert name == "list_pets"

    def test_from_summary_fallback(self) -> None:
        name = _operation_command_name(
            {"summary": "List all pets"},
            "get",
            "pets",
        )
        assert name == "list"

    def test_from_method_fallback(self) -> None:
        name = _operation_command_name({}, "get", "pets")
        assert name == "get"


# ---- _static_segments ----


class TestStaticSegments:
    def test_simple_path(self) -> None:
        assert _static_segments("/pets") == ["pets"]

    def test_with_param(self) -> None:
        assert _static_segments("/pets/{petId}") == ["pets"]

    def test_nested(self) -> None:
        assert _static_segments("/users/{userId}/pets") == ["users", "pets"]

    def test_empty(self) -> None:
        assert _static_segments("/") == []


# ---- load_spec ----


class TestLoadSpec:
    def test_local_file(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC), encoding="utf-8")
        result = load_spec(str(spec_file))
        assert result["info"]["title"] == "Pet Store"

    def test_file_not_found(self) -> None:
        with pytest.raises(UsageError, match="Spec file not found"):
            load_spec("/nonexistent/spec.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "bad.json"
        spec_file.write_text("not json", encoding="utf-8")
        with pytest.raises(UsageError, match="Invalid JSON"):
            load_spec(str(spec_file))


# ---- _build_command_tree ----


class TestBuildCommandTree:
    def test_root_name_from_title(self) -> None:
        root = _build_command_tree(SAMPLE_SPEC)
        assert root.name == "pet-store"

    def test_root_description(self) -> None:
        root = _build_command_tree(SAMPLE_SPEC)
        assert "sample pet store API" in root.description

    def test_pets_group(self) -> None:
        root = _build_command_tree(SAMPLE_SPEC)
        assert "pets" in root.subcommands

    def test_leaf_commands_under_pets(self) -> None:
        root = _build_command_tree(SAMPLE_SPEC)
        pets = root.subcommands["pets"]
        names = {name for name in pets.subcommands}
        assert "list_pets" in names
        assert "create_pet" in names
        assert "get_pet_by_id" in names
        assert "delete_pet" in names

    def test_list_pets_has_query_options(self) -> None:
        root = _build_command_tree(SAMPLE_SPEC)
        pets = root.subcommands["pets"]
        list_cmd = pets.subcommands.get("list_pets")
        assert list_cmd is not None
        assert "limit" in list_cmd.options
        assert "species" in list_cmd.options

    def test_get_pet_by_id_has_path_arg(self) -> None:
        root = _build_command_tree(SAMPLE_SPEC)
        pets = root.subcommands["pets"]
        get_cmd = pets.subcommands.get("get_pet_by_id")
        assert get_cmd is not None
        assert len(get_cmd.arguments) == 1
        assert get_cmd.arguments[0].name == "petId"

    def test_create_pet_has_data_option(self) -> None:
        root = _build_command_tree(SAMPLE_SPEC)
        pets = root.subcommands["pets"]
        create_cmd = pets.subcommands.get("create_pet")
        assert create_cmd is not None
        assert "data" in create_cmd.options

    def test_empty_paths(self) -> None:
        root = _build_command_tree({"openapi": "3.0.0", "info": {"title": "Empty"}, "paths": {}})
        assert root.name == "empty"
        assert len(root.subcommands) == 0


# ---- Cli.from_openapi integration ----


class TestCliFromOpenapi:
    def test_builds_cli(self, tmp_path: Path) -> None:
        from xclif import Cli

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC), encoding="utf-8")
        cli = Cli.from_openapi(str(spec_file))
        assert cli.root_command.name == "pet-store"
        assert "pets" in cli.root_command.subcommands

    def test_root_has_cascading_options(self, tmp_path: Path) -> None:
        from xclif import Cli

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC), encoding="utf-8")
        cli = Cli.from_openapi(str(spec_file))
        root_opts = cli.root_command.options
        assert "api_key" in root_opts
        assert "base_url" in root_opts
        assert "timeout" in root_opts
        assert root_opts["timeout"].default == 30
        assert root_opts["base_url"].default == "https://petstore.example.com/api/v1"

    def test_override_base_url(self, tmp_path: Path) -> None:
        from xclif import Cli

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC), encoding="utf-8")
        cli = Cli.from_openapi(str(spec_file), base_url="https://custom.example.com")
        assert cli.root_command.options["base_url"].default == "https://custom.example.com"

    def test_show_no_description(self, tmp_path: Path) -> None:
        from xclif import Cli

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC), encoding="utf-8")
        cli = Cli.from_openapi(str(spec_file), show_no_description=False)
        assert cli.root_command.show_no_description is False

    def test_help_shows_tree(self, tmp_path: Path, capsys) -> None:
        from xclif import Cli

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC), encoding="utf-8")
        cli = Cli.from_openapi(str(spec_file))
        # Force agent help so the full command tree (including nested leaf
        # commands) is rendered deterministically, independent of TTY/agent
        # auto-detection.
        cli.root_command.execute(["--help=agent"])
        captured = capsys.readouterr()
        assert "list_pets" in captured.out
        assert "create_pet" in captured.out
        assert "pet-store" in captured.out


# ---- _make_run_function (mocked HTTP) ----


class TestMakeRunFunction:
    """Tests for _make_run_function with mocked HTTP calls."""

    def _run_with_context(self, run_fn, *args, context=None, **kwargs):
        """Call a run function with a proper dispatch context."""
        from xclif.context import _reset_context, _set_context, Context

        ctx = context or {}
        token = _set_context(Context(ctx))
        try:
            return run_fn(*args, **kwargs)
        finally:
            _reset_context(token)

    def test_url_substitution(self, monkeypatch) -> None:
        """Verify path params are substituted into the URL template."""

        def mock_urlopen(request, **kwargs):
            class MockResponse:
                status = 200
                headers = {"Content-Type": "application/json"}

                def read(self):
                    return b'{"ok": true}'

            assert "/pets/fido" in request.full_url
            return MockResponse()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        run_fn = _make_run_function("/pets/{petId}", "GET", ["petId"], [], None)
        result = self._run_with_context(run_fn, "fido", context={"base_url": "https://api.example.com"})
        assert result == 0

    def test_query_params(self, monkeypatch) -> None:
        """Verify query params are appended to the URL."""
        urls = []

        def mock_urlopen(request, **kwargs):
            class MockResponse:
                status = 200
                headers = {"Content-Type": "application/json"}

                def read(self):
                    return b"{}"

            urls.append(request.full_url)
            return MockResponse()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        run_fn = _make_run_function("/pets", "GET", [], ["limit", "species"], None)
        result = self._run_with_context(
            run_fn, limit=10, species="cat",
            context={"base_url": "https://api.example.com"},
        )
        assert result == 0
        assert "limit=10" in urls[0]
        assert "species=cat" in urls[0]

    def test_auth_header(self, monkeypatch) -> None:
        """Verify API key is added as an auth header."""

        def mock_urlopen(request, **kwargs):
            class MockResponse:
                status = 200
                headers = {"Content-Type": "application/json"}

                def read(self):
                    return b"{}"

            assert request.headers.get("Authorization") == "Bearer mykey123"
            return MockResponse()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        run_fn = _make_run_function("/pets", "GET", [], [], None)
        result = self._run_with_context(
            run_fn,
            context={"base_url": "https://api.example.com", "api_key": "Bearer mykey123"},
        )
        assert result == 0

    def test_custom_auth_header(self, monkeypatch) -> None:
        """Verify custom API key header name is used."""

        def mock_urlopen(request, **kwargs):
            class MockResponse:
                status = 200
                headers = {"Content-Type": "application/json"}

                def read(self):
                    return b"{}"

            assert request.headers.get("X-api-key") == "secret-123"
            return MockResponse()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        run_fn = _make_run_function("/pets", "GET", [], [], None)
        result = self._run_with_context(
            run_fn,
            context={
                "base_url": "https://api.example.com",
                "api_key": "secret-123",
                "api_key_header": "X-API-Key",
            },
        )
        assert result == 0

    def test_http_error(self, monkeypatch) -> None:
        """Verify HTTP errors are handled gracefully."""

        def mock_urlopen(request, **kwargs):
            raise HTTPError(
                "http://example.com/error", 404, "Not Found", {}, None
            )

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        run_fn = _make_run_function("/nonexistent", "GET", [], [], None)
        result = self._run_with_context(run_fn, context={"base_url": "https://api.example.com"})
        assert result == 4  # 404 // 100 = 4

    def test_request_body(self, monkeypatch) -> None:
        """Verify request body is sent."""

        def mock_urlopen(request, **kwargs):
            class MockResponse:
                status = 200
                headers = {"Content-Type": "application/json"}

                def read(self):
                    return b'{"created": true}'

            assert request.data == b'{"name": "Rex", "species": "dog"}'
            assert request.headers.get("Content-type") == "application/json"
            return MockResponse()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        run_fn = _make_run_function("/pets", "POST", [], [], "data")
        result = self._run_with_context(
            run_fn, data={"name": "Rex", "species": "dog"},
            context={"base_url": "https://api.example.com"},
        )
        assert result == 0

    def test_raw_output(self, monkeypatch, capsys) -> None:
        """Verify --raw skips JSON formatting."""

        def mock_urlopen(request, **kwargs):
            class MockResponse:
                status = 200
                headers = {"Content-Type": "application/json"}

                def read(self):
                    return b'{"key": "value"}'

            return MockResponse()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        run_fn = _make_run_function("/data", "GET", [], [], None)
        result = self._run_with_context(
            run_fn,
            context={"base_url": "https://api.example.com", "raw": True},
        )
        assert result == 0
        captured = capsys.readouterr()
        assert '{"key": "value"}' in captured.out.strip()
