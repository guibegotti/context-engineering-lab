from __future__ import annotations


class ExperimentExecutionError(Exception):
    def __init__(
        self,
        code: str,
        user_message: str,
        *,
        details: str | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.details = details
        self.status_code = status_code
