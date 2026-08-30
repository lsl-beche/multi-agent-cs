"""认证路由：管理员登录/刷新Token/修改密码/获取当前用户"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db, run_sync
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter()


# ── 请求体 ───────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# ── 端点 ─────────────────────────────────────────────

@router.post("/register", summary="用户注册")
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        client_ip = request.client.host if request.client else ""
        await run_sync(db, UserService.create_user, body.username, body.password, role_name="viewer")
        result = await run_sync(db, AuthService.login, body.username, body.password, client_ip)
        return {"code": 0, "data": result, "message": "注册成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", summary="管理员登录")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        client_ip = request.client.host if request.client else ""
        result = await run_sync(db, AuthService.login, body.username, body.password, client_ip)
        return {"code": 0, "data": result, "message": "登录成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", summary="刷新令牌")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await run_sync(db, AuthService.refresh_token, body.refresh_token)
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.put("/password", summary="修改密码")
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await run_sync(db, AuthService.change_password, int(user["sub"]), body.old_password, body.new_password)
        return {"code": 0, "message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", summary="当前用户信息")
async def get_me(user: dict = Depends(current_user), db: AsyncSession = Depends(get_db)):
    try:
        info = await run_sync(db, AuthService.get_user_info, int(user["sub"]))
        return {"code": 0, "data": info}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
