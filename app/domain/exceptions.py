class DomainException(Exception):
    code: str = "DOMAIN_ERROR"


class NotFoundException(DomainException):
    code = "NOT_FOUND"


class ValidationException(DomainException):
    code = "VALIDATION_ERROR"


class ConflictException(DomainException):
    code = "CONFLICT"


class InvalidRequestException(DomainException):
    code = "INVALID_REQUEST"


class IdempotencyConflictException(DomainException):
    code = "IDEMPOTENCY_CONFLICT"


class ReserveFailedException(DomainException):
    code = "RESERVE_FAILED"

    def __init__(
        self,
        message: str = "Failed to reserve order items",
        *,
        failed_items: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.failed_items = failed_items or []


class MissingCartIdentityException(DomainException):
    code = "MISSING_CART_IDENTITY"


class UnauthorizedException(DomainException):
    code = "UNAUTHORIZED"


class PermissionDeniedException(DomainException):
    code = "PERMISSION_DENIED"


class UpstreamServiceUnavailableException(DomainException):
    code = "UPSTREAM_SERVICE_UNAVAILABLE"


class B2BUnavailableException(DomainException):
    code = "B2B_UNAVAILABLE"
