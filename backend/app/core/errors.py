import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def error_response(
    status: int, code: str, message: str, headers: Optional[dict[str, str]] = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("invalid request: %s", exc.errors())
        return error_response(400, "invalid_request", "The request was malformed.")

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return error_response(exc.status_code, code, str(exc.detail))

    # A middleware rather than an Exception handler: Starlette runs Exception
    # handlers outside CORSMiddleware, so the browser would see a CORS failure
    # instead of this JSON body.
    @app.middleware("http")
    async def _unexpected_error(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("unhandled error on %s %s", request.method, request.url.path)
            return error_response(500, "internal_error", "Something went wrong. Please try again.")
