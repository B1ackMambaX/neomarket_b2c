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


class CancelNotAllowedException(DomainException):
    code = "CANCEL_NOT_ALLOWED"

    def __init__(self, current_status: str) -> None:
        super().__init__(
            f"Order cancellation is not allowed in status {current_status}"
        )
        self.current_status = current_status


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


class CategoryNotFoundException(NotFoundException):
    pass


class CategoryHierarchyBrokenException(ValidationException):
    code = "ORPHAN_NODE"


class BreadcrumbParamsException(InvalidRequestException):
    code = "AMBIGUOUS_PARAM"

class ProductNotFoundException(DomainException):
    code = "PRODUCT_NOT_FOUND"


class SubscriptionAlreadyExistsException(DomainException):
    code = "SUBSCRIPTION_ALREADY_EXISTS"


class InvalidNotifyOnException(DomainException):
    code = "INVALID_NOTIFY_ON"
