"""Unit tests for xclif.config — config file loading and key resolution."""

import json
from pathlib import Path

import tomlkit

from xclif.config import load_config, resolve_key


def test_load_toml(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('name = "Alice"\ncount = 42\n')
    result = load_config(tmp_path)
    assert result == {"name": "Alice", "count": 42}


def test_load_json(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"name": "Bob"}))
    result = load_config(tmp_path)
    assert result == {"name": "Bob"}


def test_toml_preferred_over_json(tmp_path):
    (tmp_path / "config.toml").write_text('name = "from_toml"\n')
    (tmp_path / "config.json").write_text(json.dumps({"name": "from_json"}))
    result = load_config(tmp_path)
    assert result["name"] == "from_toml"


def test_missing_config_returns_empty(tmp_path):
    result = load_config(tmp_path)
    assert result == {}


def test_resolve_key_flat():
    data = {"name": "Alice", "count": 42}
    assert resolve_key(data, "name") == "Alice"
    assert resolve_key(data, "count") == 42


def test_resolve_key_dotted():
    data = {"greeter": {"name": "Alice"}}
    assert resolve_key(data, "greeter.name") == "Alice"


def test_resolve_key_deeply_nested():
    data = {"a": {"b": {"c": "deep"}}}
    assert resolve_key(data, "a.b.c") == "deep"


def test_resolve_key_missing_returns_sentinel():
    data = {"name": "Alice"}
    sentinel = object()
    assert resolve_key(data, "missing", sentinel) is sentinel


def test_resolve_key_missing_nested_returns_sentinel():
    data = {"a": {"b": 1}}
    sentinel = object()
    assert resolve_key(data, "a.c", sentinel) is sentinel


def test_resolve_key_intermediate_not_dict_returns_sentinel():
    data = {"a": "not_a_dict"}
    sentinel = object()
    assert resolve_key(data, "a.b", sentinel) is sentinel
