class QuestError(Exception):
    """Safe product error: no SQL, private context or hidden quest content."""

    def __init__(self, code: str, status_code: int, message: str,
                 retryable: bool = False, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.details = details
