import types
from pathlib import Path
from typing import Annotated, Callable, Literal, Union, get_args, get_origin

__all__ = ["annotation2converter", "is_list_type", "unwrap_list", "unwrap_param_metadata", "unwrap_with_config"]

type ScalarParameterTypes = str | int | float | bool | Path
type ParameterTypes = ScalarParameterTypes | list[ScalarParameterTypes]
_default_converters = {str: str, int: int, float: float, bool: bool, Path: Path}


def unwrap_with_config(annotation) -> tuple[type, "WithConfig | None"]:
    """Unwrap an annotation that may be Annotated[T, WithConfig(...)].

    Returns (inner_type, with_config_instance) or (annotation, None).
    """
    from xclif import WithConfig

    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        inner_type = args[0]
        for metadata in args[1:]:
            if isinstance(metadata, WithConfig):
                return inner_type, metadata
    return annotation, None


def unwrap_optional(x):
    """Unwrap Optional[X] / X | None to X.

    Returns the single non-``None`` member of a ``Union`` (typing.Union or
    PEP 604 ``X | None``). Non-unions and unions without exactly one non-None
    member are returned unchanged.
    """
    if get_origin(x) in (Union, types.UnionType):
        non_none = [a for a in get_args(x) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return x


def unwrap_list(x):
    """Unwrap list[X] to X.

    Returns the element type of a ``list[X]`` generic. Non-list annotations
    and bare ``list`` (no element type) are returned unchanged.
    """
    if get_origin(x) is list:
        args = get_args(x)
        if args:
            return args[0]
    return x


def annotation2converter[T: ParameterTypes, Y](x: T) -> None | Callable[[T], Y]:
    # Unwrap Optional[X] / X | None → inner type (nullable options)
    x = unwrap_optional(x)
    # Check for list[X] generics (e.g. list[str], list[int])
    if get_origin(x) is list:
        element = unwrap_list(x)
        if element in _default_converters:
            return _default_converters[element]
        return None
    if get_origin(x) is Literal:
        choices = get_args(x)
        if not all(isinstance(c, str) for c in choices):
            return None
        choices_set = set(choices)
        choices_str = "|".join(choices)
        def _literal_converter(value: str, _choices=choices_set, _str=choices_str) -> str:
            if value not in _choices:
                raise ValueError(f"expected one of: {_str}, got {value!r}")
            return value
        _literal_converter.__choices__ = list(choices)
        return _literal_converter
    return _default_converters.get(x)


def is_list_type(x) -> bool:
    """Return True if the annotation is a list[X] generic."""
    return get_origin(x) is list


def unwrap_param_metadata(annotation):
    """Extract Arg, Option, WithConfig, and Cascade from an Annotated annotation.

    Returns (inner_type, arg_meta, option_meta, with_config, cascade).
    For plain (non-Annotated) types, returns (annotation, None, None, None, False).
    """
    from xclif import Arg, Cascade, Option, WithConfig

    if get_origin(annotation) is not Annotated:
        return annotation, None, None, None, False

    args = get_args(annotation)
    inner_type = args[0]
    arg_meta = None
    opt_meta = None
    with_config = None
    cascade = False

    for metadata in args[1:]:
        if isinstance(metadata, Arg):
            arg_meta = metadata
        elif isinstance(metadata, Option):
            opt_meta = metadata
        elif isinstance(metadata, WithConfig):
            with_config = metadata
        elif isinstance(metadata, Cascade):
            cascade = True

    return inner_type, arg_meta, opt_meta, with_config, cascade
