import math
from typing import Optional, Tuple
from sqlmodel import Session, select
from app.models.delivery import DeliveryProfile
from app.models.user import User
from app.models.enums import UserRole

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth in km.
    """
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)

def find_best_delivery_partner(
    session: Session,
    restaurant_lat: float,
    restaurant_lon: float
) -> Optional[User]:
    """
    Smart Delivery Partner Assignment:
    Finds available delivery partners, scores by:
    1. Distance to restaurant pickup (Haversine)
    2. Driver rating
    3. Availability flag
    Returns best matching partner or fallback delivery user.
    """
    profiles = session.exec(
        select(DeliveryProfile).where(DeliveryProfile.is_available == True)
    ).all()

    if not profiles:
        # Fallback to demo delivery partner if no profile is explicitly free
        fallback = session.exec(
            select(User).where(User.role == UserRole.DELIVERY_PARTNER)
        ).first()
        return fallback

    best_partner_user_id = None
    min_cost_score = float("inf")

    for p in profiles:
        dist = haversine_distance_km(restaurant_lat, restaurant_lon, p.current_latitude, p.current_longitude)
        # Cost score: shorter distance is better, higher rating is better
        # Lower cost score is optimal
        cost_score = (dist * 2.0) - (p.rating * 1.5)
        if cost_score < min_cost_score:
            min_cost_score = cost_score
            best_partner_user_id = p.user_id

    if best_partner_user_id:
        return session.exec(select(User).where(User.id == best_partner_user_id)).first()

    return session.exec(select(User).where(User.role == UserRole.DELIVERY_PARTNER)).first()

def calculate_delivery_eta(distance_km: float, prep_time_minutes: int) -> int:
    """
    Calculates estimated time of arrival (minutes):
    Prep time + (Distance * 4.5 minutes/km in city traffic) + 5 min buffer.
    """
    transit_time = int(distance_km * 4.5)
    return prep_time_minutes + max(transit_time, 10) + 5
