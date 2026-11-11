"""Small, consistent application errors for API responses."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, status_code: int, message: str, code: str = "error") -> None:
        self.status_code = status_code
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(404, message, "not_found")


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to do that.") -> None:
        super().__init__(403, message, "forbidden")


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(409, message, "conflict")


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(422, message, "validation_error")


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Sign in is required.") -> None:
        super().__init__(401, message, "unauthorized")
