"""Tests for the examples.

Covers both examples under examples/:
  - greeter   (also tested more deeply in test_integration_greeter.py)
  - poetry-clone

The poetry-clone tests mock subprocess.call so they don't require a real
`poetry` installation.
"""

from unittest.mock import patch

import pytest

from xclif import Cli
from xclif.command import Command


# ===========================================================================
# greeter — structure tests
# ===========================================================================


class TestGreeterStructure:
    @pytest.fixture(scope="class")
    def cli(self):
        from greeter import routes
        return Cli.from_routes(routes)

    def test_builds_successfully(self, cli):
        assert isinstance(cli.root_command, Command)

    def test_root_name(self, cli):
        assert cli.root_command.name == "greeter"

    def test_has_greet_subcommand(self, cli):
        assert "greet" in cli.root_command.subcommands

    def test_has_config_subcommand(self, cli):
        assert "config" in cli.root_command.subcommands

    def test_config_has_set_and_get(self, cli):
        config = cli.root_command.subcommands["config"]
        assert "set" in config.subcommands
        assert "get" in config.subcommands

    def test_has_completions_subcommand(self, cli):
        assert "completions" in cli.root_command.subcommands

    def test_greet_has_name_option(self, cli):
        greet = cli.root_command.subcommands["greet"]
        assert "name" in greet.options

    def test_greet_has_template_option(self, cli):
        greet = cli.root_command.subcommands["greet"]
        assert "template" in greet.options

    def test_config_set_has_name_option(self, cli):
        config_set = cli.root_command.subcommands["config"].subcommands["set"]
        assert "name" in config_set.options

    def test_config_set_has_template_option(self, cli):
        config_set = cli.root_command.subcommands["config"].subcommands["set"]
        assert "template" in config_set.options


# ===========================================================================
# poetry-clone — structure tests
# ===========================================================================


class TestPoetryCloneStructure:
    @pytest.fixture(scope="class")
    def cli(self):
        from poetry import routes
        return Cli.from_routes(routes)

    def test_builds_successfully(self, cli):
        assert isinstance(cli.root_command, Command)

    def test_root_name(self, cli):
        assert cli.root_command.name == "poetry"

    def test_has_env_subcommand(self, cli):
        assert "env" in cli.root_command.subcommands

    def test_has_self_subcommand(self, cli):
        assert "self" in cli.root_command.subcommands

    def test_env_has_use_subcommand(self, cli):
        assert "use" in cli.root_command.subcommands["env"].subcommands

    def test_self_has_update_subcommand(self, cli):
        assert "update" in cli.root_command.subcommands["self"].subcommands

    def test_self_has_show_subcommand(self, cli):
        assert "show" in cli.root_command.subcommands["self"].subcommands

    def test_self_show_has_plugins_subcommand(self, cli):
        show = cli.root_command.subcommands["self"].subcommands["show"]
        assert "plugins" in show.subcommands

    def test_env_use_has_python_argument(self, cli):
        use = cli.root_command.subcommands["env"].subcommands["use"]
        assert any(a.name == "python" for a in use.arguments)

    def test_self_update_has_preview_option(self, cli):
        update = cli.root_command.subcommands["self"].subcommands["update"]
        assert "preview" in update.options

    def test_has_completions_subcommand(self, cli):
        assert "completions" in cli.root_command.subcommands


# ===========================================================================
# poetry-clone — execution tests (subprocess mocked)
# ===========================================================================


class TestPoetryCloneExecution:
    @pytest.fixture(scope="class")
    def cli(self):
        from poetry import routes
        return Cli.from_routes(routes)

    @pytest.fixture
    def root(self, cli):
        return cli.root_command

    def test_root_no_args_prints_help(self, root, capsys):
        result = root.execute([])
        assert result == 0
        assert capsys.readouterr().out != ""

    def test_root_help_returns_zero(self, root, capsys):
        result = root.execute(["--help"])
        assert result == 0

    def test_env_use_delegates_to_poetry(self, root):
        with patch("poetry.routes.env.use.subprocess.call", return_value=0) as mock_call:
            result = root.execute(["env", "use", "3.11"])
        assert result == 0
        mock_call.assert_called_once()
        cmd = mock_call.call_args[0][0]
        assert cmd == ["poetry", "env", "use", "3.11"]

    def test_env_use_forwards_exit_code(self, root):
        with patch("poetry.routes.env.use.subprocess.call", return_value=1):
            result = root.execute(["env", "use", "3.11"])
        assert result == 1

    def test_env_use_missing_python_arg_errors(self, root, capsys):
        result = root.execute(["env", "use"])
        assert result == 2
        assert "Missing required argument" in capsys.readouterr().err

    def test_self_update_delegates_to_poetry(self, root):
        with patch("poetry.routes.self.update.subprocess.call", return_value=0) as mock_call:
            result = root.execute(["self", "update"])
        assert result == 0
        cmd = mock_call.call_args[0][0]
        assert cmd == ["poetry", "self", "update"]
        assert "--preview" not in cmd

    def test_self_update_with_preview_flag(self, root):
        with patch("poetry.routes.self.update.subprocess.call", return_value=0) as mock_call:
            result = root.execute(["self", "update", "--preview"])
        assert result == 0
        cmd = mock_call.call_args[0][0]
        assert "--preview" in cmd

    def test_self_update_forwards_exit_code(self, root):
        with patch("poetry.routes.self.update.subprocess.call", return_value=42):
            result = root.execute(["self", "update"])
        assert result == 42

    def test_self_show_plugins_delegates_to_poetry(self, root):
        with patch("poetry.routes.self.show.plugins.subprocess.call", return_value=0) as mock_call:
            result = root.execute(["self", "show", "plugins"])
        assert result == 0
        cmd = mock_call.call_args[0][0]
        assert cmd == ["poetry", "self", "show", "plugins"]

    def test_self_show_plugins_forwards_exit_code(self, root):
        with patch("poetry.routes.self.show.plugins.subprocess.call", return_value=1):
            result = root.execute(["self", "show", "plugins"])
        assert result == 1

    def test_env_help_returns_zero(self, root, capsys):
        result = root.execute(["env", "--help"])
        assert result == 0

    def test_self_help_returns_zero(self, root, capsys):
        result = root.execute(["self", "--help"])
        assert result == 0

    def test_unknown_subcommand_returns_error(self, root, capsys):
        result = root.execute(["doesnotexist"])
        assert result == 2
        assert "Unknown" in capsys.readouterr().err
