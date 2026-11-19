import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select, col, func

from app.database import get_session
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.order import Order
from app.models.enums import UserRole, OrderStatus
from app.models.delivery import DeliveryProfile
from app.services.auth_service import require_role
from app.services.auth_service import get_password_hash

router = APIRouter(prefix="/api/superadmin", tags=["Super Admin"])


class DeliveryPartnerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    phone: Optional[str] = Field(default=None, max_length=20)
    vehicle_type: str = Field(default="Motorcycle", min_length=2, max_length=50)
    vehicle_number: str = Field(default="Not provided", min_length=2, max_length=30)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address")
        return email

    @field_validator("full_name", "phone", "vehicle_type", "vehicle_number")
    @classmethod
    def trim_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("Name must contain at least 2 characters")
        return value.strip()

    @field_validator("vehicle_type", "vehicle_number")
    @classmethod
    def validate_vehicle_details(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("Vehicle details must contain at least 2 characters")
        return value.strip()

    @field_validator("password")
    @classmethod
    def validate_bcrypt_password_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or fewer")
        return value


@router.post("/delivery-partners", status_code=201)
def create_delivery_partner(
    partner_in: DeliveryPartnerCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session),
):
    """Create a delivery account and its initially offline dispatch profile."""
    email = partner_in.email
    existing = session.exec(select(User).where(func.lower(User.email) == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=email,
        hashed_password=get_password_hash(partner_in.password),
        full_name=partner_in.full_name,
        phone=partner_in.phone or None,
        role=UserRole.DELIVERY_PARTNER,
        is_active=True,
        loyalty_points=0,
    )
    try:
        session.add(user)
        session.flush()
        profile = DeliveryProfile(
            user_id=user.id,
            vehicle_type=partner_in.vehicle_type,
            vehicle_number=partner_in.vehicle_number,
            is_available=False,
        )
        session.add(profile)
        session.commit()
        session.refresh(user)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from error

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "is_available": False,
    }

@router.get("/stats")
def get_superadmin_stats(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    users = session.exec(select(User)).all()
    restaurants = session.exec(select(Restaurant)).all()
    orders = session.exec(select(Order)).all()

    total_gmv = sum(o.total_amount for o in orders if o.status != OrderStatus.CANCELLED)
    platform_commission = round(total_gmv * 0.15, 2)  # 15% platform commission

    role_breakdown = {}
    for u in users:
        role_breakdown[u.role.value] = role_breakdown.get(u.role.value, 0) + 1

    return {
        "total_users": len(users),
        "total_restaurants": len(restaurants),
        "total_orders": len(orders),
        "total_gmv": round(total_gmv, 2),
        "platform_revenue": platform_commission,
        "role_breakdown": role_breakdown,
        "active_restaurants": len([r for r in restaurants if r.is_active])
    }

@router.get("/users")
def list_all_users(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    users = session.exec(select(User).order_by(col(User.id).asc())).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "loyalty_points": u.loyalty_points,
            "joined": u.created_at.strftime("%b %d, %Y")
        }
        for u in users
    ]

@router.patch("/users/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    target = session.exec(select(User).where(User.id == user_id)).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot deactivate Super Admin")

    target.is_active = not target.is_active
    session.add(target)
    session.commit()
    return {"message": f"User status updated to {'Active' if target.is_active else 'Deactivated'}"}

@router.get("/restaurants")
def list_all_restaurants(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    return session.exec(select(Restaurant)).all()

@router.patch("/restaurants/{restaurant_id}/toggle-status")
def toggle_restaurant_status(
    restaurant_id: int,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant = session.exec(select(Restaurant).where(Restaurant.id == restaurant_id)).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    restaurant.is_active = not restaurant.is_active
    session.add(restaurant)
    session.commit()
    return {"message": f"Restaurant is now {'Active' if restaurant.is_active else 'Deactivated'}"}
