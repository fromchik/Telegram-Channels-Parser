class DomainError(Exception):
    """Base domain exception."""


class AccessDeniedError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class DuplicateError(DomainError):
    pass


class ExternalServiceError(DomainError):
    pass
