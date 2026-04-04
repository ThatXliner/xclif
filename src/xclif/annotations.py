from typing import Annotated, Callable, get_args, get_origin

type ScalarParameterTypes = str | int | float | bool
type ParameterTypes = ScalarParameterTypes | list[ScalarParameterTypes]
_default_converters = {str: str, int: int, float: float, bool: bool}


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


def annotation2converter[T: ParameterTypes, Y](x: T) -> None | Callable[[T], Y]:
    # Check for list[X] generics (e.g. list[str], list[int])
    origin = get_origin(x)
    if origin is list:
        args = get_args(x)
        if args and args[0] in _default_converters:
            return _default_converters[args[0]]
        return None
    return _default_converters.get(x)


def is_list_type(x) -> bool:
    """Return True if the annotation is a list[X] generic."""
    return get_origin(x) is list


def unwrap_param_metadata(annotation):
    """Extract Arg, Option, and WithConfig from an Annotated annotation.

    Returns (inner_type, arg_meta, option_meta, with_config).
    For plain (non-Annotated) types, returns (annotation, None, None, None).
    """
    from xclif import Arg, Option, WithConfig

    if get_origin(annotation) is not Annotated:
        return annotation, None, None, None

    args = get_args(annotation)
    inner_type = args[0]
    arg_meta = None
    opt_meta = None
    with_config = None

    for metadata in args[1:]:
        if isinstance(metadata, Arg):
            arg_meta = metadata
        elif isinstance(metadata, Option):
            opt_meta = metadata
        elif isinstance(metadata, WithConfig):
            with_config = metadata

    return inner_type, arg_meta, opt_meta, with_config
