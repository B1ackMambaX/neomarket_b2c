class DomainException(Exception):
    code: str = "DOMAIN_ERROR"


class NotFoundException(DomainException):
    code = "NOT_FOUND"


class ValidationException(DomainException):
    code = "VALIDATION_ERROR"


class PermissionDeniedException(DomainException):
    code = "PERMISSION_DENIED"
