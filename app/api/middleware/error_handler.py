from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    B2BUnavailableException,
    DomainException,
    ConflictException,
    IdempotencyConflictException,
    InvalidRequestException,
    MissingCartIdentityException,
    NotFoundException,
    PermissionDeniedException,
    ReserveFailedException,
    UnauthorizedException,
    UpstreamServiceUnavailableException,
)

_STATUS_MAP = {
    ConflictException: 409,
    IdempotencyConflictException: 409,
    InvalidRequestException: 400,
    MissingCartIdentityException: 400,
    NotFoundException: 404,
    PermissionDeniedException: 403,
    ReserveFailedException: 409,
    UnauthorizedException: 401,
    B2BUnavailableException: 503,
    UpstreamServiceUnavailableException: 502,
}

_HTTP_CODE_MAP = {
    400: "INVALID_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


async def domain_exception_handler(
    request: Request,
    exc: DomainException,
) -> JSONResponse:
    status_code = _STATUS_MAP.get(type(exc), 400)
    content = {"code": exc.code, "message": str(exc)}
    if isinstance(exc, ReserveFailedException):
        content["failed_items"] = exc.failed_items
    return JSONResponse(
        status_code=status_code,
        content=content,
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": _HTTP_CODE_MAP.get(exc.status_code, "HTTP_ERROR"),
            "message": str(exc.detail),
        },
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": exc.errors(),
        },
    )
