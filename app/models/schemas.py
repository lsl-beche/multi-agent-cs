"""Pydantic模型：API请求/响应体定义（CS客服 + 管理后台）"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ============================================================
# CS Agent 客服模型（原有）
# ============================================================


class Role(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Message(BaseModel):
    role: Role
    content: str
    timestamp: datetime | None = None


class ChatRequest(BaseModel):
    session_id: str
    user_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    intent: str | None = None
    need_human: bool = False
    suggestions: list[str] = Field(default_factory=list)


class TicketCreate(BaseModel):
    session_id: str
    user_id: str
    order_id: str | None = None
    category: str
    description: str


class TicketOut(BaseModel):
    ticket_id: str
    status: str = "pending"
    created_at: datetime | None = None


class KnowledgeItem(BaseModel):
    question: str
    answer: str
    category: str | None = None


# ============================================================
# 通用模型
# ============================================================

class ApiResponse(BaseModel):
    code: int = 0
    data: Any = None
    message: str = "ok"


class PaginatedResponse(BaseModel):
    code: int = 0
    data: list[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    message: str = "ok"


# ============================================================
# 认证 (auth)
# ============================================================

class AuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4)


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class AuthPasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# ============================================================
# 商品管理 (admin/products)
# ============================================================

class SkuCreate(BaseModel):
    sku_code: str
    spec_info: dict = {}
    price: float
    original_price: float | None = None
    barcode: str | None = None
    stock: int = 0


class ImageCreate(BaseModel):
    url: str
    sort_order: int = 0
    is_main: bool = False


class ProductCreate(BaseModel):
    spu_code: str
    name: str
    subtitle: str | None = None
    category_id: int | None = None
    brand: str | None = None
    main_image: str | None = None
    description: str | None = None
    status: str = "draft"
    images: list[ImageCreate] = []
    skus: list[SkuCreate] = []


class ProductUpdate(BaseModel):
    name: str | None = None
    subtitle: str | None = None
    category_id: int | None = None
    brand: str | None = None
    main_image: str | None = None
    description: str | None = None
    images: list[ImageCreate] | None = None


class CategoryCreate(BaseModel):
    name: str
    parent_id: int | None = None
    level: int = 1
    sort_order: int = 0


# ============================================================
# 订单管理 (admin/orders)
# ============================================================

class OrderShipRequest(BaseModel):
    carrier: str = Field(..., min_length=1)
    tracking_no: str | None = None


class OrderCancelRequest(BaseModel):
    reason: str | None = None


# ============================================================
# 库存管理 (admin/inventory)
# ============================================================

class InventoryAdjustRequest(BaseModel):
    sku_id: int
    change_qty: int
    reason: str = "manual"


# ============================================================
# 用户管理 (admin/users)
# ============================================================

class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)
    email: str | None = None
    phone: str | None = None
    role: str = "viewer"


class AdminUserUpdate(BaseModel):
    email: str | None = None
    phone: str | None = None
    status: str | None = None


# ============================================================
# 营销管理 (admin/marketing)
# ============================================================

class CouponCreate(BaseModel):
    name: str
    coupon_type: str = "fixed"  # fixed / percent
    threshold: float = 0
    value: float
    total_count: int
    user_limit: int = 1
    start_time: str  # ISO datetime
    end_time: str


class CouponGrantRequest(BaseModel):
    user_ids: list[int]


class PromotionCreate(BaseModel):
    name: str
    promo_type: str
    rules: dict
    product_ids: list[int] = []
    start_time: str
    end_time: str


# ============================================================
# 评价管理 (admin/reviews)
# ============================================================

class ReviewReplyRequest(BaseModel):
    reply: str


# ============================================================
# 退款 (admin/payments)
# ============================================================

class RefundApproveRequest(BaseModel):
    approved: bool = True


# ============================================================
# C 端请求 DTO（减少路由直接使用 dict）
# ============================================================


class CartQuantityRequest(BaseModel):
    quantity: int = Field(1, ge=1)


class CartSelectRequest(BaseModel):
    selected: bool = True


class PaymentInitiateRequest(BaseModel):
    order_id: int
    channel: str = "wechat"


class PaymentConfirmRequest(BaseModel):
    payment_no: str
    signature: str
    timestamp: int = 0


class ReviewSubmitRequest(BaseModel):
    order_id: int
    product_id: int
    rating: int = Field(..., ge=1, le=5)
    content: str = ""
    is_anonymous: bool = False


class AddressCreateRequest(BaseModel):
    receiver_name: str = Field(..., min_length=1, max_length=64)
    receiver_phone: str = Field(..., min_length=6, max_length=20)
    province: str = Field(..., min_length=1, max_length=32)
    city: str = Field(..., min_length=1, max_length=32)
    district: str = Field(..., min_length=1, max_length=32)
    detail: str = Field(..., min_length=1, max_length=256)
    is_default: bool = False


class AddressUpdateRequest(AddressCreateRequest):
    pass


class ProfileUpdateRequest(BaseModel):
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=128)


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)
