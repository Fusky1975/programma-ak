class K1ParseError(ValueError):
    """Raised when a .K1 move-submission file doesn't match the expected shape."""

    def __init__(self, message: str, *, line_number: int | None = None, line: str | None = None):
        self.line_number = line_number
        self.line = line
        location = f" (line {line_number}: {line!r})" if line_number is not None else ""
        super().__init__(f"{message}{location}")
