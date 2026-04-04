from xclif import WithConfig, command


@command()
def _(name: WithConfig[str] = "", template: WithConfig[str] = "Hello, {}!") -> None:
    """Greet someone by name.

    NAME defaults to the value stored in config (via `config set`).
    TEMPLATE defaults to "Hello, {}!" or the value stored in config.
    """
    if not name:
        print("Error: please provide a name or set one with `greeter config set name <name>`")
        return
    print(template.format(name))
