import importlib
import pkgutil
import types


def is_private_route_module(module_name: str) -> bool:
    """Return True if any dotted module segment is private."""
    return any(
        part.startswith("_") and part not in {"__init__", "__main__"}
        for part in module_name.split(".")
    )


def get_modules(package: types.ModuleType) -> list[tuple[str, types.ModuleType]]:
    return [
        (name, importlib.import_module(name))
        for _, name, __ in pkgutil.walk_packages(
            package.__path__,
            package.__name__ + ".",
        )
        if not is_private_route_module(name.removeprefix(package.__name__ + "."))
    ]
