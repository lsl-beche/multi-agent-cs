"""用户服务：CRUD + 地址管理 + 封禁"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import Address, Role, User, UserRole


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
