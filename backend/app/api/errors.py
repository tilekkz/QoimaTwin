"""The HTTP boundary uses the same JSON error envelope as the CLI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.errors import AppError, InvalidInputError, error_report


class UnexpectedExecutionError(AppError):
    code = "execution_error"


def attach_error_handlers(app: FastAPI) -> None:
    async def domain_error(_request: Request, exc: Exception) -> JSONResponse:
        error = (
            exc
            if isinstance(exc, AppError)
            else UnexpectedExecutionError("unexpected backend execution failure")
        )
        return JSONResponse(error_report(error), status_code=error.http_status)

    async def invalid_request(_request: Request, exc: Exception) -> JSONResponse:
        message = "invalid request"
        if isinstance(exc, RequestValidationError):
            codes = sorted({str(error["type"]) for error in exc.errors()})
            message = f"request validation failed: {', '.join(codes)}"
        return JSONResponse(error_report(InvalidInputError(message)), status_code=422)

    async def http_error(_request: Request, exc: Exception) -> JSONResponse:
        status = exc.status_code if isinstance(exc, HTTPException) else 500
        return JSONResponse(error_report(AppError(str(exc))), status_code=status)

    app.add_exception_handler(AppError, domain_error)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, domain_error)
