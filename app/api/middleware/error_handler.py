from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainException, NotFoundException, PermissionDeniedException

_STATUS_MAP = {
    NotFoundException: 404,
    PermissionDeniedException: 403,
}


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    status_code = _STATUS_MAP.get(type(exc), 400)
    return JSONResponse(
        status_code=status_code,
        content={"error": exc.code, "message": str(exc)},
    )
