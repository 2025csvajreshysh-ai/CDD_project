"""Geospatial helpers and delivery dispatch policy."""
import math
from typing import Any, Optional, cast

from sqlmodel import Session, select, col

from app.models.delivery import DeliveryProfile
from app.models.enums import OrderStatus, UserRole
from app.models.order import Order
from app.models.user import User

EARTH_RADIUS_KM = 6371.0088
CITY_SPEED_KMH = 25.0
ETA_BUFFER_MINUTES = 5


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km; inputs are decimal latitude/longitude."""
    if not all(math.isfinite(v) for v in (lat1, lon1, lat2, lon2)):
        raise ValueError("Coordinates must be finite numbers")
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("Latitude must be between -90 and 90")
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError("Longitude must be between -180 and 180")
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    a = min(1.0, max(0.0, a))
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_eta_minutes(distance_km: float, remaining_prep_minutes: int) -> int:
    if distance_km < 0 or remaining_prep_minutes < 0:
        raise ValueError("Distance and prep time cannot be negative")
    travel_minutes = distance_km / CITY_SPEED_KMH * 60
    return math.ceil(remaining_prep_minutes + travel_minutes + ETA_BUFFER_MINUTES)


def assign_nearest_available_partner(session: Session, order: Order, restaurant_lat: float, restaurant_lon: float) -> Optional[User]:
    """Assign the closest available rider with no active order, or fallback to the least busy rider."""
    if order.id is None:
        return None
    profiles = session.exec(select(DeliveryProfile).where(col(DeliveryProfile.is_available).is_(True))).all()
    candidates: list[tuple[float, float, int, User]] = []
    active_statuses = [OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY]
    
    # 1. Look for available riders who are completely free (0 active orders)
    for profile in profiles:
        active = session.exec(select(Order).where(
            Order.delivery_partner_id == profile.user_id,
            col(Order.status).in_(active_statuses),
            Order.id != order.id,
        )).first()
        user = session.get(User, profile.user_id)
        if active is None and user is not None and user.id is not None and user.is_active and user.role == UserRole.DELIVERY_PARTNER:
            distance = haversine_distance_km(restaurant_lat, restaurant_lon, profile.current_latitude, profile.current_longitude)
            candidates.append((distance, -profile.rating, user.id, user))
    if candidates:
        return min(candidates, key=lambda candidate: candidate[:3])[3]

    # 2. Fallback: if all riders have an ongoing trip, assign to the online rider with the fewest active orders
    least_busy_candidates: list[tuple[int, float, float, int, User]] = []
    for profile in profiles:
        user = session.get(User, profile.user_id)
        if user is not None and user.id is not None and user.is_active and user.role == UserRole.DELIVERY_PARTNER:
            active_count = len(session.exec(select(Order).where(
                Order.delivery_partner_id == profile.user_id,
                col(Order.status).in_(active_statuses),
                Order.id != order.id,
            )).all())
            distance = haversine_distance_km(restaurant_lat, restaurant_lon, profile.current_latitude, profile.current_longitude)
            least_busy_candidates.append((active_count, distance, -profile.rating, user.id, user))
    if least_busy_candidates:
        return min(least_busy_candidates, key=lambda candidate: candidate[:4])[4]

    # 3. Final fallback: any registered and active delivery partner in the system
    fallback_user = session.exec(
        select(User).where(User.role == UserRole.DELIVERY_PARTNER, User.is_active == True)
    ).first()
    return fallback_user
