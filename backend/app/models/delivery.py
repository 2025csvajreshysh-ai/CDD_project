from datetime import datetime
from typing import ClassVar, Optional
from sqlmodel import SQLModel, Field
from app.models.common import utc_now

class DeliveryProfile(SQLModel, table=True):
    __tablename__: ClassVar[str] = "delivery_profiles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    vehicle_type: str = Field(default="Motorcycle", max_length=50)
    vehicle_number: str = Field(default="KA-01-EF-2026", max_length=30)
    current_latitude: float = Field(default=12.9716)
    current_longitude: float = Field(default=77.5946)
    is_available: bool = Field(default=True, index=True)
    total_deliveries: int = Field(default=0)
    total_earnings: float = Field(default=0.0)
    rating: float = Field(default=4.8)
    last_location_updated: datetime = Field(default_factory=utc_now)

class DeliveryAssignment(SQLModel, table=True):
    __tablename__: ClassVar[str] = "delivery_assignments"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", unique=True, index=True)
    delivery_partner_id: int = Field(foreign_key="users.id", index=True)
    assigned_at: datetime = Field(default_factory=utc_now)
    accepted_at: Optional[datetime] = Field(default=None)
    picked_up_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    delivery_fee_earned: float = Field(default=40.0)
    distance_km: float = Field(default=3.2)
