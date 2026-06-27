"""Tests for the ``python -m xclif`` developer CLI."""

from xclif import __main__ as main_module


def test_compile_command_writes_manifest_to_output_dir(tmp_path, capsys):
    exit_code = main_module.root.execute(
        ["compile", "greeter.routes", "--output", str(tmp_path)],
        context={"configure_logging": False},
    )

    manifest = tmp_path / "_xclif_manifest.py"
    captured = capsys.readouterr()

    assert exit_code == 0
    assert manifest.exists()
    assert "def _build_cli(" in manifest.read_text(encoding="utf-8")
    assert f"Written: {manifest}" in captured.out


def test_compile_command_reports_import_errors(capsys):
    exit_code = main_module.root.execute(
        ["compile", "not_a_real_routes_module"],
        context={"configure_logging": False},
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Cannot import 'not_a_real_routes_module'" in captured.err
