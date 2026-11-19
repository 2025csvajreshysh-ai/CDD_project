"""Shared tenant-scoped access checks for restaurant data."""
from typing import List, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.enums import UserRole
from app.models.restaurant import Restaurant
from app.models.user import User


def get_restaurant_scope(
    session: Session,
    current_user: User,
    restaurant_id: Optional[int] = None,
) -> Optional[List[int]]:
    """Return visible restaurant IDs, or ``None`` for an unrestricted super admin."""
    if current_user.role == UserRole.SUPER_ADMIN:
        if restaurant_id is not None and session.get(Restaurant, restaurant_id) is None:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        return [restaurant_id] if restaurant_id is not None else None

    if current_user.role != UserRole.RESTAURANT_ADMIN:
        raise HTTPException(status_code=403, detail="Restaurant administrator access is required")

    owned_ids = session.exec(
        select(Restaurant.id).where(Restaurant.owner_id == current_user.id)
    ).all()
    if restaurant_id is not None and restaurant_id not in owned_ids:
        raise HTTPException(status_code=403, detail="You can only access your own restaurants")
    return [restaurant_id] if restaurant_id is not None else owned_ids
