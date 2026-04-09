"""Unit tests for WithConfig annotation."""

from typing import Annotated, get_args, get_origin, get_type_hints
from unittest.mock import patch

from xclif import Cli, WithConfig
from xclif import Arg, Option as OptionMeta
from xclif.command import Command, command, extract_parameters
from xclif.definition import Argument, _DefinitionOption


def test_with_config_getitem_still_works():
    """WithConfig[str] should still produce Annotated[str, WithConfig()]."""
    result = WithConfig[str]
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is str
    assert isinstance(args[1], WithConfig)


def test_with_config_getitem_int():
    result = WithConfig[int]
    args = get_args(result)
    assert args[0] is int
    assert isinstance(args[1], WithConfig)



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


def test_with_config_is_frozen():
    import pytest
    wc = WithConfig()
    with pytest.raises((AttributeError, TypeError)):
        wc.x = 1  # type: ignore[attr-defined]


def test_with_config_has_no_fields():
    """WithConfig should be a no-argument marker after simplification."""
    wc = WithConfig()
    assert not hasattr(wc, 'env')
    assert not hasattr(wc, 'key')


def test_arg_metadata():
    from xclif import Arg
    a = Arg(description="A file", name="FILE")
    assert a.description == "A file"
    assert a.name == "FILE"


def test_arg_defaults():
    from xclif import Arg
    a = Arg()
    assert a.description is None
    assert a.name is None


def test_option_metadata():
    from xclif import Option as OptionMeta
    o = OptionMeta(description="Dry run", name="dry-run")
    assert o.description == "Dry run"
    assert o.name == "dry-run"


def test_option_defaults():
    from xclif import Option as OptionMeta
    o = OptionMeta()
    assert o.description is None
    assert o.name is None


def test_arg_is_frozen():
    from xclif import Arg
    a = Arg(description="x")
    try:
        a.description = "y"
        assert False, "Should have raised"
    except (AttributeError, TypeError):
        pass


def test_option_is_frozen():
    from xclif import Option as OptionMeta
    o = OptionMeta(description="x")
    try:
        o.description = "y"
        assert False, "Should have raised"
    except (AttributeError, TypeError):
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
        options={"greeting": _DefinitionOption("greeting", str, "desc", "default", config=WithConfig())},
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


def test_deep_merge():
    from xclif import _deep_merge

    base = {"a": 1, "b": {"x": 10, "y": 20}, "c": 3}
    override = {"b": {"y": 99, "z": 30}, "d": 4}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": {"x": 10, "y": 99, "z": 30}, "c": 3, "d": 4}
    # Originals unchanged
    assert base["b"] == {"x": 10, "y": 20}


def test_local_config_overrides_user_config(tmp_path, monkeypatch):
    """local_config file in cwd overrides user-level config values."""
    # User-level config
    (tmp_path / "user_config").mkdir()
    (tmp_path / "user_config" / "config.toml").write_text('greeting = "from_user"\n')

    # Local config in cwd
    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / ".myapp.toml").write_text('greeting = "from_local"\n')
    monkeypatch.chdir(cwd)

    received = {}

    @command("myapp")
    def root() -> None:
        """Test app."""

    greet_cmd = Command(
        "greet",
        lambda greeting="default": received.update(greeting=greeting) or 0,
        options={"greeting": _DefinitionOption("greeting", str, "desc", "default", config=WithConfig())},
    )
    root.subcommands["greet"] = greet_cmd

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path / "user_config")):
        cli = Cli(root_command=root, local_config=".myapp.toml")

    context = {"env_prefix": cli.env_prefix, "config_data": cli._config_data}
    root.execute(["greet"], context)
    assert received["greeting"] == "from_local"


def test_local_config_merges_with_user_config(tmp_path, monkeypatch):
    """Local config merges with user config; keys only in user config are preserved."""
    (tmp_path / "user_config").mkdir()
    (tmp_path / "user_config" / "config.toml").write_text(
        'greeting = "from_user"\nname = "Alice"\n'
    )

    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / ".myapp.toml").write_text('greeting = "from_local"\n')
    monkeypatch.chdir(cwd)

    received = {}

    @command("myapp")
    def root() -> None:
        """Test app."""

    greet_cmd = Command(
        "greet",
        lambda greeting="default", name="nobody": received.update(greeting=greeting, name=name) or 0,
        options={
            "greeting": _DefinitionOption("greeting", str, "desc", "default", config=WithConfig()),
            "name": _DefinitionOption("name", str, "desc", "nobody", config=WithConfig()),
        },
    )
    root.subcommands["greet"] = greet_cmd

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path / "user_config")):
        cli = Cli(root_command=root, local_config=".myapp.toml")

    context = {"env_prefix": cli.env_prefix, "config_data": cli._config_data}
    root.execute(["greet"], context)
    assert received["greeting"] == "from_local"
    assert received["name"] == "Alice"  # preserved from user config


def test_local_config_not_loaded_when_not_set(tmp_path, monkeypatch):
    """When local_config is None, cwd files are ignored."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / ".myapp.toml").write_text('greeting = "from_local"\n')
    monkeypatch.chdir(cwd)

    received = {}

    @command("myapp")
    def root() -> None:
        """Test app."""

    greet_cmd = Command(
        "greet",
        lambda greeting="default": received.update(greeting=greeting) or 0,
        options={"greeting": _DefinitionOption("greeting", str, "desc", "default", config=WithConfig())},
    )
    root.subcommands["greet"] = greet_cmd

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path / "empty")):
        (tmp_path / "empty").mkdir()
        cli = Cli(root_command=root)  # no local_config

    context = {"env_prefix": cli.env_prefix, "config_data": cli._config_data}
    root.execute(["greet"], context)
    assert received["greeting"] == "default"


def test_local_config_missing_file_is_fine(tmp_path, monkeypatch):
    """If local_config is set but the file doesn't exist, nothing happens."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    @command("myapp")
    def root() -> None:
        """Test app."""

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root, local_config=".myapp.toml")

    assert cli._config_data == {}


def test_local_config_json(tmp_path, monkeypatch):
    """local_config works with .json files too."""
    import json

    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / ".myapp.json").write_text(json.dumps({"greeting": "from_json"}))
    monkeypatch.chdir(cwd)

    received = {}

    @command("myapp")
    def root() -> None:
        """Test app."""

    greet_cmd = Command(
        "greet",
        lambda greeting="default": received.update(greeting=greeting) or 0,
        options={"greeting": _DefinitionOption("greeting", str, "desc", "default", config=WithConfig())},
    )
    root.subcommands["greet"] = greet_cmd

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path / "empty")):
        (tmp_path / "empty").mkdir()
        cli = Cli(root_command=root, local_config=".myapp.json")

    context = {"env_prefix": cli.env_prefix, "config_data": cli._config_data}
    root.execute(["greet"], context)
    assert received["greeting"] == "from_json"
