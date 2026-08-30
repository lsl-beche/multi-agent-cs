"""认证服务：登录/注册/密码修改/JWT签发"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.tables import Permission, Role, RolePermission, User, UserRole
from app.services.async_bridge import async_adapter

# 角色⇄权限映射（与 seed_data 保持一致）
ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "super_admin": [
        "products:create", "products:read", "products:update", "products:delete", "products:export",
        "orders:create", "orders:read", "orders:update", "orders:delete", "orders:export",
        "users:create", "users:read", "users:update", "users:delete", "users:export",
        "inventory:read", "inventory:update", "inventory:export",
        "payments:read", "payments:update", "payments:export",
        "shipments:create", "shipments:read", "shipments:update",
        "coupons:create", "coupons:read", "coupons:update", "coupons:delete",
        "promotions:create", "promotions:read", "promotions:update", "promotions:delete",
        "reviews:read", "reviews:update",
        "reports:read", "reports:export",
        "logs:read",
        "tickets:create", "tickets:read", "tickets:update",
        "system:read", "system:update",
    ],
    "admin": [
        "products:create", "products:read", "products:update", "products:export",
        "orders:create", "orders:read", "orders:update", "orders:export",
        "users:read", "users:update",
        "inventory:read", "inventory:update", "inventory:export",
        "payments:read", "payments:update", "payments:export",
        "shipments:create", "shipments:read", "shipments:update",
        "coupons:create", "coupons:read", "coupons:update",
        "promotions:create", "promotions:read", "promotions:update",
        "reviews:read", "reviews:update",
        "reports:read", "reports:export",
        "logs:read",
        "tickets:create", "tickets:read", "tickets:update",
    ],
    "operator": [
        "products:read", "products:update",
        "orders:read", "orders:update",
        "users:read",
        "inventory:read", "inventory:update",
        "payments:read",
        "shipments:read", "shipments:update",
        "coupons:read",
        "promotions:read",
        "reviews:read", "reviews:update",
        "reports:read",
        "logs:read",
        "tickets:read", "tickets:update",
    ],
    "viewer": [
        "products:read", "orders:read", "users:read",
        "inventory:read", "payments:read", "shipments:read",
        "coupons:read", "promotions:read", "reviews:read",
        "reports:read", "logs:read", "tickets:read",
    ],
}


class AuthService:

    @staticmethod
    def _get_user_permissions(db: Session, user: User) -> tuple[str, list[str]]:
        """获取用户角色和权限列表（优先读 DB role_permissions，无数据时回退内置映射）"""
        role_row = db.execute(
            select(Role.name).join(UserRole).where(UserRole.user_id == user.id)
        ).scalars().first()
        role_name = role_row or "viewer"

        role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
        permissions: list[str] = []
        if role:
            try:
                rows = db.execute(
                    select(Permission.resource, Permission.action)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == role.id)
                ).all()
            except Exception:
                # role_permissions 尚未迁移时回退内置映射，避免登录直接失败
                rows = []
            permissions = [f"{r}:{a}" for r, a in rows]

        if not permissions:
            # role_permissions 未灌数据（未跑 seed）时回退内置映射，避免全部 403
            permissions = ROLE_PERMISSION_MAP.get(role_name, ROLE_PERMISSION_MAP["viewer"])
        return role_name, permissions

    @staticmethod
    def login(db: Session, username: str, password: str, client_ip: str = "") -> dict:
        from app.core.login_guard import check_login_allowed, record_login_failure, reset_login_attempts

        # 登录防爆破检查
        allowed, reason = check_login_allowed(username, client_ip)
        if not allowed:
            raise ValueError(reason)

        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            record_login_failure(username, client_ip)
            raise ValueError("用户名或密码错误")
        if user.status != "active":
            raise ValueError("账户已被禁用")

        # 登录成功，重置计数
        reset_login_attempts(username)

        user.last_login = datetime.utcnow()
        db.commit()

        role_name, permissions = AuthService._get_user_permissions(db, user)

        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": role_name,
            "permissions": permissions,
        }
        return {
            "access_token": create_access_token(payload),
            "refresh_token": create_refresh_token(payload),
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": role_name,
            },
        }

    @staticmethod
    def refresh_token(db: Session, token: str) -> dict:
        """刷新令牌：从 DB 重新查询用户权限（防止降权后旧权限续命）"""
        try:
            payload = decode_token(token)
            if payload.get("type") != "refresh":
                raise ValueError("令牌类型错误")
        except Exception:
            raise ValueError("无效的刷新令牌")

        # 从 DB 重新获取用户信息和权限（关键安全修复）
        user_id = int(payload["sub"])
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")
        if user.status != "active":
            raise ValueError("账户已被禁用")

        role_name, permissions = AuthService._get_user_permissions(db, user)

        new_payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": role_name,
            "permissions": permissions,
        }
        return {
            "access_token": create_access_token(new_payload),
            "refresh_token": create_refresh_token(new_payload),
            "token_type": "bearer",
        }

    @staticmethod
    def change_password(db: Session, user_id: int, old_pwd: str, new_pwd: str) -> None:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")
        if not verify_password(old_pwd, user.password_hash):
            raise ValueError("旧密码错误")
        user.password_hash = hash_password(new_pwd)
        db.commit()

    @staticmethod
    def get_user_info(db: Session, user_id: int) -> dict:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")

        role_name, permissions = AuthService._get_user_permissions(db, user)

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "role": role_name,
            "permissions": permissions,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }


AuthService.login_async = async_adapter(AuthService.login)
AuthService.refresh_token_async = async_adapter(AuthService.refresh_token)
AuthService.change_password_async = async_adapter(AuthService.change_password)
AuthService.get_user_info_async = async_adapter(AuthService.get_user_info)
