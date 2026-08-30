"""用户服务：CRUD + 地址管理 + 封禁"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import Address, Role, User, UserRole
from app.repositories import AddressRepository, UserRepository
from app.services.async_bridge import async_adapter


class UserService:

    @staticmethod
    def get_points(db: Session, user_id: int) -> dict:
        """查询用户积分"""
        u = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not u:
            raise ValueError("用户不存在")
        return {"user_id": u.id, "points": u.points or 0}

    @staticmethod
    def get_member_info(db: Session, user_id: int) -> dict:
        """查询会员等级（按积分阈值推导）与积分"""
        u = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not u:
            raise ValueError("用户不存在")
        points = u.points or 0
        if points >= 2000:
            level = "黑金会员"
        elif points >= 1000:
            level = "黄金会员"
        elif points >= 500:
            level = "白银会员"
        else:
            level = "普通会员"
        return {
            "user_id": u.id,
            "username": u.username,
            "points": points,
            "level": level,
        }

    @staticmethod
    def list_users(db: Session, page: int = 1, page_size: int = 20,
                   keyword: str | None = None, status: str | None = None) -> tuple[list[dict], int]:
        from app.core.pagination import paginate

        query = select(User)

        if keyword:
            query = query.where(
                User.username.ilike(f"%{keyword}%") |
                User.email.ilike(f"%{keyword}%") |
                User.phone.ilike(f"%{keyword}%")
            )
        if status:
            query = query.where(User.status == status)

        rows, total = paginate(db, query, page, page_size, order_by=User.id.desc())

        # 为每个用户查询角色
        result = []
        for u in rows:
            role_row = db.execute(select(Role.name).join(UserRole).where(UserRole.user_id == u.id)).scalars().first()
            result.append({
                "id": u.id, "username": u.username, "email": u.email,
                "phone": u.phone, "status": u.status, "role": role_row or "viewer",
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            })
        return result, total

    @staticmethod
    def create_user(db: Session, username: str, password: str,
                    email: str | None = None, phone: str | None = None, role_name: str = "viewer") -> dict:
        existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            raise ValueError(f"用户名 {username} 已存在")

        user = User(
            username=username,
            password_hash=hash_password(password),
            email=email,
            phone=phone,
        )
        db.add(user)
        db.flush()

        role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
        if role:
            db.add(UserRole(user_id=user.id, role_id=role.id))

        db.commit()
        return {"id": user.id, "username": user.username}

    @staticmethod
    def update_user(db: Session, user_id: int, email: str | None = None,
                    phone: str | None = None, status: str | None = None) -> dict:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if status is not None:
            user.status = status
        db.commit()
        return {"id": user.id, "username": user.username, "status": user.status}

    @staticmethod
    def ban_user(db: Session, user_id: int) -> dict:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")
        user.status = "banned" if user.status == "active" else "active"
        db.commit()
        return {"id": user.id, "status": user.status}

    @staticmethod
    def get_addresses(db: Session, user_id: int) -> list[dict]:
        rows = db.execute(
            select(Address).where(Address.user_id == user_id).order_by(Address.is_default.desc())
        ).scalars().all()
        return [{
            "id": a.id, "receiver": a.receiver, "phone": a.phone,
            "province": a.province, "city": a.city, "district": a.district,
            "detail": a.detail, "is_default": a.is_default,
        } for a in rows]

    @staticmethod
    async def get_addresses_async(db: AsyncSession, user_id: int) -> list[dict]:
        rows = await AddressRepository(db).list_by_user(user_id)
        return [{
            "id": a.id, "receiver": a.receiver, "phone": a.phone,
            "province": a.province, "city": a.city, "district": a.district,
            "detail": a.detail, "is_default": a.is_default,
        } for a in rows]

    @staticmethod
    async def create_address_async(db: AsyncSession, user_id: int, data: dict) -> dict:
        repo = AddressRepository(db)
        if data.get("is_default"):
            await repo.clear_default(user_id)
        addr = Address(
            user_id=user_id,
            receiver=data.get("receiver_name", ""),
            phone=data.get("receiver_phone", ""),
            province=data.get("province", ""),
            city=data.get("city", ""),
            district=data.get("district", ""),
            detail=data.get("detail", ""),
            is_default=bool(data.get("is_default")),
        )
        await repo.add(addr)
        await repo.commit()
        await db.refresh(addr)
        return {
            "id": addr.id, "receiver": addr.receiver, "phone": addr.phone,
            "province": addr.province, "city": addr.city, "district": addr.district,
            "detail": addr.detail, "is_default": addr.is_default,
        }

    @staticmethod
    async def update_address_async(db: AsyncSession, user_id: int, address_id: int, data: dict) -> dict:
        repo = AddressRepository(db)
        addr = await repo.get_by_id(address_id, user_id)
        if not addr:
            raise ValueError("地址不存在")
        if data.get("is_default"):
            await repo.clear_default(user_id)
        addr.receiver = data.get("receiver_name", addr.receiver)
        addr.phone = data.get("receiver_phone", addr.phone)
        addr.province = data.get("province", addr.province)
        addr.city = data.get("city", addr.city)
        addr.district = data.get("district", addr.district)
        addr.detail = data.get("detail", addr.detail)
        addr.is_default = bool(data.get("is_default", addr.is_default))
        await repo.commit()
        return {"id": addr.id, "receiver": addr.receiver, "phone": addr.phone, "is_default": addr.is_default}

    @staticmethod
    async def delete_address_async(db: AsyncSession, user_id: int, address_id: int) -> None:
        repo = AddressRepository(db)
        addr = await repo.get_by_id(address_id, user_id)
        if not addr:
            raise ValueError("地址不存在")
        await repo.delete(addr)
        await repo.commit()

    @staticmethod
    async def update_profile_async(db: AsyncSession, user_id: int, data: dict) -> None:
        repo = UserRepository(db)
        user = await repo.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        if "phone" in data:
            user.phone = data["phone"]
        if "email" in data:
            user.email = data["email"]
        await repo.commit()

    @staticmethod
    async def change_password_async(db: AsyncSession, user_id: int, old_pwd: str, new_pwd: str) -> None:
        from app.core.security import verify_password

        repo = UserRepository(db)
        user = await repo.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        if not verify_password(old_pwd, user.password_hash):
            raise ValueError("原密码错误")
        if len(new_pwd) < 6:
            raise ValueError("新密码至少6位")
        user.password_hash = hash_password(new_pwd)
        await repo.commit()


UserService.list_users_async = async_adapter(UserService.list_users)
UserService.create_user_async = async_adapter(UserService.create_user)
UserService.update_user_async = async_adapter(UserService.update_user)
UserService.ban_user_async = async_adapter(UserService.ban_user)
