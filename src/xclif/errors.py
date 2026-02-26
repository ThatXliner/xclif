# Not a dataclass: Exception.__init__ requires explicit super().__init__()
# to set the message, which a dataclass-generated __init__ would not do.
class UsageError(Exception):
    """A user-facing CLI invocation error."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint
