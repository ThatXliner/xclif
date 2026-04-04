"""Unit tests for WithConfig annotation."""

from typing import Annotated, get_args, get_origin, get_type_hints

from xclif import WithConfig


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
