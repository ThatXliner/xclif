"""Unit tests for WithConfig annotation."""

from typing import Annotated, get_args, get_origin, get_type_hints
from unittest.mock import patch

from xclif import Cli, WithConfig
from xclif.command import Command, command, extract_parameters
from xclif.definition import Argument, Option


def test_with_config_getitem_returns_annotated():
    """WithConfig[str] should produce Annotated[str, WithConfig()]."""
    result = WithConfig[str]
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is str
    assert isinstance(args[1], WithConfig)
    assert args[1].env is None
    assert args[1].key is None


def test_with_config_getitem_int():
    result = WithConfig[int]
    args = get_args(result)
    assert args[0] is int
    assert isinstance(args[1], WithConfig)


def test_with_config_explicit_annotated():
    """Annotated[str, WithConfig(env="MY_VAR")] should work directly."""
    hint = Annotated[str, WithConfig(env="MY_VAR", key="custom_key")]
    args = get_args(hint)
    assert args[0] is str
    assert args[1].env == "MY_VAR"
    assert args[1].key == "custom_key"


def test_with_config_in_function_signature():
    """WithConfig[str] in a real function signature should be detectable."""
    def f(name: WithConfig[str]) -> None: ...

    hints = get_type_hints(f, include_extras=True)
    ann = hints["name"]
    assert get_origin(ann) is Annotated
    args = get_args(ann)
    assert args[0] is str
    assert isinstance(args[1], WithConfig)


def test_with_config_equality():
    assert WithConfig() == WithConfig()
    assert WithConfig(env="A") == WithConfig(env="A")
    assert WithConfig(env="A") != WithConfig(env="B")


def test_with_config_is_frozen():
    wc = WithConfig()
    try:
        wc.env = "X"
        assert False, "Should have raised"
    except AttributeError:
        pass


def test_full_priority_cli_over_env_over_config_over_default(tmp_path, monkeypatch):
    """End-to-end: CLI > env > config > default."""
    (tmp_path / "config.toml").write_text('greeting = "from_config"\n')
    monkeypatch.setenv("MYAPP_GREETING", "from_env")

    received = {}

    @command("myapp")
    def root() -> None:
        """Test app."""

    greet_cmd = Command(
        "greet",
        lambda greeting="default": received.update(greeting=greeting) or 0,
        options={"greeting": Option("greeting", str, "desc", "default", config=WithConfig())},
    )
    root.subcommands["greet"] = greet_cmd

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root)

    context = {"env_prefix": cli.env_prefix, "config_data": cli._config_data}

    # CLI wins
    received.clear()
    root.execute(["greet", "--greeting", "from_cli"], context)
    assert received["greeting"] == "from_cli"

    # Env wins over config
    received.clear()
    root.execute(["greet"], context)
    assert received["greeting"] == "from_env"

    # Config wins over default (unset env)
    monkeypatch.delenv("MYAPP_GREETING")
    received.clear()
    root.execute(["greet"], context)
    assert received["greeting"] == "from_config"

    # Default when no env or config
    received.clear()
    empty_context = {"env_prefix": "MYAPP", "config_data": {}}
    root.execute(["greet"], empty_context)
    assert received["greeting"] == "default"


def test_with_config_argument_from_config(tmp_path):
    """WithConfig on a required argument resolves from config file."""
    (tmp_path / "config.toml").write_text('name = "ConfigAlice"\n')

    received = []

    @command("myapp")
    def root() -> None:
        """Test app."""

    greet_cmd = Command(
        "greet",
        lambda name: received.append(name) or 0,
        arguments=[Argument("name", str, "desc", config=WithConfig())],
    )
    root.subcommands["greet"] = greet_cmd

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root)

    context = {"env_prefix": cli.env_prefix, "config_data": cli._config_data}
    root.execute(["greet"], context)
    assert received == ["ConfigAlice"]
