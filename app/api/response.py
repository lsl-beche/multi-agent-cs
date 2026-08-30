"""统一 API 响应与业务异常"""
from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 0
    data: Any = None
    message: str = "ok"


def ok(data: Any = None, message: str = "ok", code: int = 0) -> dict:
    """成功响应统一结构"""
    return {"code": code, "data": data, "message": message}


class BusinessError(Exception):
    """业务异常：可映射为统一 HTTP 错误"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: int | None = None,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code if code is not None else status_code
        self.data = data


class NotFoundError(BusinessError):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message, status_code=404, code=404)


class ForbiddenError(BusinessError):
    def __init__(self, message: str = "没有权限") -> None:
        super().__init__(message, status_code=403, code=403)


class UnauthorizedError(BusinessError):
    def __init__(self, message: str = "未认证") -> None:
        super().__init__(message, status_code=401, code=401)
