import inspect
import sys
import types
from dataclasses import dataclass, field
from typing import NoReturn, Self

from xclif.command import Command, command
from xclif.definition import Option
from xclif.importer import get_modules

__all__ = ["Cli", "WithConfig", "command"]


@dataclass(frozen=True)
class WithConfig:
    """Marker for parameters that can be read from a config file or env var.

    ``name: WithConfig[str]`` is sugar for ``Annotated[str, WithConfig()]``.
    Use ``Annotated[str, WithConfig(env="MY_VAR", key="custom")]`` for overrides.

    Priority order: CLI flag > env var > config file > default.
    See: https://github.com/ThatXliner/xclif/issues/23
    """

    env: str | None = None
    key: str | None = None

    def __class_getitem__(cls, item: type) -> type:
        from typing import Annotated
        return Annotated[item, cls()]


def _detect_version(package_name: str) -> str | None:
    """Try to auto-detect the version from installed package metadata."""
    import importlib.metadata
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


@dataclass
class Cli:
    """The main API for Xclif."""

    root_command: Command
    version: str | None = None
    env_prefix: str | None = None
    config_name: str | None = None
    _config_data: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        from pathlib import Path

        import platformdirs

        from xclif.completions import make_completions_command
        from xclif.config import load_config

        # Derive defaults from root command name
        if self.env_prefix is None:
            self.env_prefix = self.root_command.name.upper()
        if self.config_name is None:
            self.config_name = self.root_command.name

        # Load config file
        config_dir = Path(platformdirs.user_config_dir(self.config_name))
        self._config_data = load_config(config_dir)

        # Add completions subcommand
        self.root_command._assert_no_arguments(adding="completions")
        self.root_command.subcommands["completions"] = make_completions_command(
            self.root_command
        )

        # Inject --version as an implicit option on root command only
        self.root_command.implicit_options["version"] = Option(
            "version", bool, "Print program version and exit",
        )
        self.root_command.version = self.version

        # Auto-inject config subcommand if any WithConfig params exist
        from xclif.config_commands import _has_with_config, make_config_command

        if "config" not in self.root_command.subcommands and _has_with_config(self.root_command):
            self.root_command.subcommands["config"] = make_config_command(config_dir)

        # Validate WithConfig conflicts
        from xclif.validation import check_with_config_conflicts
        check_with_config_conflicts(self.root_command, self.env_prefix)

    def __call__(self) -> NoReturn:
        context = {"env_prefix": self.env_prefix, "config_data": self._config_data}
        sys.exit(self.root_command.execute(context=context))

    def add_command(self, path: list[str], command: Command) -> None:
        cursor = self.root_command
        for part in path[:-1]:
            if cursor.arguments:
                msg = "Cannot add subcommands to a command with arguments"
                raise ValueError(msg)
            cursor = cursor.subcommands.setdefault(
                part, Command(part, lambda: 0)
            )
        cursor._assert_no_arguments(adding=command.name)
        cursor.subcommands[command.name] = command

    @classmethod
    def from_manifest(
        cls,
        manifest: types.ModuleType,
        *,
        version: str | None = None,
        env_prefix: str | None = None,
        config_name: str | None = None,
    ) -> Self:
        """Load a pre-compiled manifest produced by ``xclif compile``.

        This is a faster alternative to :meth:`from_routes` — it skips the
        ``pkgutil.walk_packages`` + ``inspect.getmembers`` filesystem scan at
        the cost of a one-time ``xclif compile`` build step.

        Parameters
        ----------
        manifest:
            The generated manifest module (typically ``myapp._xclif_manifest``).
        version:
            Explicit version string.  When *None*, auto-detected from the
            top-level package of *manifest* (same behaviour as
            :meth:`from_routes`).
        """
        build_fn = getattr(manifest, "_build_cli", None)
        if build_fn is None:
            raise ImportError(
                f"Manifest module {manifest.__name__!r} has no '_build_cli' function. "
                "Re-run `python -m xclif compile <routes_module>` to regenerate it."
            )
        if version is None and manifest.__package__:
            package_name = manifest.__package__.split(".")[0]
            version = _detect_version(package_name)
        return build_fn(version=version, env_prefix=env_prefix, config_name=config_name)

    @classmethod
    def from_routes(
        cls,
        routes: types.ModuleType,
        *,
        version: str | None = None,
        env_prefix: str | None = None,
        config_name: str | None = None,
    ) -> Self:
        members = inspect.getmembers(routes, lambda x: isinstance(x, Command))

        if len(members) > 1:
            msg = f"Multiple commands found in root module ({routes.__name__!r})"
            raise ValueError(msg)
        elif len(members) == 0:
            msg = f"No commands found in root module ({routes.__name__!r})"
            raise ValueError(msg)
        if routes.__package__ is None:
            msg = f"Root module ({routes.__name__!r}) must be part of a package"
            raise ImportError(msg)

        # Auto-detect version if not explicitly provided
        if version is None:
            package_name = routes.__package__.split(".")[0]
            version = _detect_version(package_name)

        root_path = routes.__package__ + "."
        root_command = members[0][1]
        if root_command.name is None:
            msg = "Root command must have a name (it will determine the program name)"
            raise ValueError(msg)
        output = cls(root_command=root_command, version=version, env_prefix=env_prefix, config_name=config_name)
        for path, module in get_modules(routes):
            members = inspect.getmembers(module, lambda x: isinstance(x, Command))
            if not members:
                continue
            if len(members) > 1:
                msg = f"Multiple commands found in {path!r}"
                raise ValueError(msg)
            _name, function = members[0]
            output.add_command(path.removeprefix(root_path).split("."), function)
        return output
