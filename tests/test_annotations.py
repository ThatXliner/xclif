"""Unit tests for xclif.annotations."""
import pytest
from typing import Literal, Optional, Union
from xclif.annotations import annotation2converter


def test_literal_converter_accepts_valid_value():
    conv = annotation2converter(Literal["bash", "zsh", "fish"])
    assert conv("bash") == "bash"
    assert conv("zsh") == "zsh"
    assert conv("fish") == "fish"


def test_literal_converter_rejects_invalid_value():
    conv = annotation2converter(Literal["bash", "zsh", "fish"])
    with pytest.raises(ValueError, match="bash.*zsh.*fish"):
        conv("powershell")


def test_literal_returns_none_for_mixed_types():
    result = annotation2converter(Literal["a", 1])
    assert result is None


def test_literal_single_value():
    conv = annotation2converter(Literal["only"])
    assert conv("only") == "only"


def test_non_literal_unchanged():
    assert annotation2converter(str) is str
    assert annotation2converter(int) is int


def test_unwraps_optional_pep604():
    assert annotation2converter(str | None) is str
    assert annotation2converter(int | None) is int


def test_unwraps_optional_typing():
    assert annotation2converter(Optional[str]) is str
    assert annotation2converter(Optional[int]) is int


def test_unwraps_optional_around_literal():
    conv = annotation2converter(Optional[Literal["a", "b"]])
    assert conv("a") == "a"
    with pytest.raises(ValueError, match="a.*b"):
        conv("c")


def test_ambiguous_union_unsupported():
    # More than one non-None member → cannot pick a converter.
    assert annotation2converter(int | str) is None
    assert annotation2converter(Union[int, str, None]) is None
