from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    DomainException,
    ConflictException,
    MissingCartIdentityException,
    NotFoundException,
    PermissionDeniedException,
    UnauthorizedException,
    UpstreamServiceUnavailableException,
)

_STATUS_MAP = {
    ConflictException: 409,
    MissingCartIdentityException: 400,
    NotFoundException: 404,
    PermissionDeniedException: 403,
    UnauthorizedException: 401,
    UpstreamServiceUnavailableException: 502,
}


async def domain_exception_handler(
    request: Request,
    exc: DomainException,
) -> JSONResponse:
    status_code = _STATUS_MAP.get(type(exc), 400)
    return JSONResponse(
        status_code=status_code,
        content={"code": exc.code, "message": str(exc)},
    )
