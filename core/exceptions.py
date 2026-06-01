class AppException(Exception):
    def __init__(self, message: str, code: int = 5000):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(AppException):
    def __init__(self, message: str):
        super().__init__(message, code=1001)


class NotFoundError(AppException):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(f"{resource} not found: {resource_id}", code=1002)


class AIGenerationError(AppException):
    def __init__(self, message: str):
        super().__init__(f"AI generation failed: {message}", code=2001)


class AITimeoutError(AppException):
    def __init__(self, timeout: float):
        super().__init__(f"AI generation timed out after {timeout}s", code=2002)


class ReviewRejectedError(AppException):
    def __init__(self, reason: str):
        super().__init__(f"Content review rejected: {reason}", code=3001)


class PlatformAuthError(AppException):
    def __init__(self, message: str = "Platform authentication failed"):
        super().__init__(message, code=4001)


class PublishError(AppException):
    def __init__(self, message: str):
        super().__init__(f"Publish failed: {message}", code=4002)


class PublishTimeoutError(AppException):
    def __init__(self, timeout: float):
        super().__init__(f"Publish timed out after {timeout}s", code=4003)
