"""Stable errors shared by command-line and HTTP boundaries."""

from pathlib import Path


class AppError(Exception):
    code = "application_error"
    http_status = 500


class InvalidInputError(AppError, ValueError):
    code = "invalid_input"
    http_status = 422


class OutputNotEmptyError(AppError, ValueError):
    code = "output_not_empty"
    http_status = 409


def require_empty_output(path: Path, *, allow_inputs: bool = False) -> None:
    if not path.exists():
        return
    if not path.is_dir():
        raise OutputNotEmptyError(f"output must be an empty directory: {path}")
    entries = list(path.iterdir())
    if allow_inputs and len(entries) == 1 and entries[0].name == "inputs" and entries[0].is_dir():
        return
    if entries:
        raise OutputNotEmptyError(f"output must be an empty directory: {path}")


def error_report(exc: Exception) -> dict[str, object]:
    code = exc.code if isinstance(exc, AppError) else "execution_error"
    return {
        "status": "failed",
        "issues": [str(exc)],
        "error": {"code": code, "message": str(exc)},
    }
