from xclif import command


@command()
def poetry() -> None:
    """A Poetry clone built with Xclif. Delegates to the real `poetry` binary."""
