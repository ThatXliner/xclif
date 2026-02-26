"""Unit tests for xclif.parser."""

import pytest

from xclif.definition import Option
from xclif.parser import flatten_dict_values, parse_options


# ---------------------------------------------------------------------------
# flatten_dict_values
# ---------------------------------------------------------------------------


def test_flatten_single_value():
    assert flatten_dict_values({"a": [1]}) == {"a": 1}


def test_flatten_multi_value_stays_list():
    assert flatten_dict_values({"a": [1, 2]}) == {"a": [1, 2]}


def test_flatten_mixed():
    result = flatten_dict_values({"a": [1], "b": [2, 3]})
    assert result == {"a": 1, "b": [2, 3]}


def test_flatten_empty():
    assert flatten_dict_values({}) == {}


# ---------------------------------------------------------------------------
# parse_options — bool flags (no value consumed)
# ---------------------------------------------------------------------------


def _bool_option(name: str) -> dict[str, Option]:
    return {name: Option(name, bool, "A boolean flag")}


def test_bool_flag_sets_true():
    result = parse_options(_bool_option("verbose"), ["--verbose"])
    assert result == {"verbose": [True]}


def test_bool_flag_multiple():
    result = parse_options(_bool_option("verbose"), ["--verbose", "--verbose"])
    assert result == {"verbose": [True, True]}


def test_bool_flag_empty_args():
    result = parse_options(_bool_option("verbose"), [])
    assert result == {}


# ---------------------------------------------------------------------------
# parse_options — value options (consume next token)
# ---------------------------------------------------------------------------


def _str_option(name: str) -> dict[str, Option]:
    return {name: Option(name, str, "A string option")}


def _int_option(name: str) -> dict[str, Option]:
    return {name: Option(name, int, "An int option")}


def test_str_option_value():
    result = parse_options(_str_option("name"), ["--name", "Alice"])
    assert result == {"name": ["Alice"]}


def test_int_option_value():
    result = parse_options(_int_option("count"), ["--count", "42"])
    assert result == {"count": [42]}


def test_option_with_hyphen_in_name():
    opts = {"dry_run": Option("dry_run", bool, "Dry run flag")}
    result = parse_options(opts, ["--dry-run"])
    assert result == {"dry_run": [True]}


def test_multiple_different_options():
    opts = {
        "name": Option("name", str, "Name"),
        "verbose": Option("verbose", bool, "Verbose"),
    }
    result = parse_options(opts, ["--name", "Bob", "--verbose"])
    assert result == {"name": ["Bob"], "verbose": [True]}


def test_repeated_value_option():
    opts = {"tag": Option("tag", str, "Tag")}
    result = parse_options(opts, ["--tag", "foo", "--tag", "bar"])
    assert result == {"tag": ["foo", "bar"]}


# ---------------------------------------------------------------------------
# parse_options — error cases
# ---------------------------------------------------------------------------


def test_unknown_option_raises():
    with pytest.raises(RuntimeError, match="Unknown option --nope"):
        parse_options({}, ["--nope"])


def test_value_option_missing_value_raises():
    opts = _str_option("name")
    with pytest.raises(RuntimeError, match="requires a value"):
        parse_options(opts, ["--name"])


def test_unexpected_positional_raises():
    with pytest.raises(RuntimeError, match="Unexpected argument"):
        parse_options({}, ["notanoption"])


def test_short_option_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        parse_options({}, ["-v"])


def test_double_dash_raises_not_implemented():
    opts = _bool_option("verbose")
    with pytest.raises(NotImplementedError):
        parse_options(opts, ["--"])
