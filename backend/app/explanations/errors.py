"""Stable public failures; never include provider content, request objects or credentials."""


class ExplanationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Mercury explanation {code}")
