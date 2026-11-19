from datetime import datetime
from typing import Optional, List, ClassVar, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.common import utc_now

if TYPE_CHECKING:
    from app.models.menu import MenuItem
    from app.models.inventory import Ingredient
    from app.models.order import Order
    from app.models.waste import FoodWasteRecord

class Restaurant(SQLModel, table=True):
    __tablename__: ClassVar[str] = "restaurants"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=120)
    tagline: Optional[str] = Field(default=None, max_length=200)
    description: str = Field(max_length=1000)
    cuisine_type: str = Field(default="Multi-Cuisine", max_length=100)
    address: str = Field(max_length=255)
    city: str = Field(default="Bangalore", max_length=100)
    phone: str = Field(default="+91 98765 43210", max_length=20)
    rating: float = Field(default=4.5)
    total_reviews: int = Field(default=0)
    image_url: str = Field(max_length=500)
    banner_url: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)
    is_pure_veg: bool = Field(default=False)
    delivery_time_mins: int = Field(default=30)
    cost_for_two: float = Field(default=300.0)
    latitude: float = Field(default=12.9716)
    longitude: float = Field(default=77.5946)
    owner_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=utc_now)
    
    # Relationships
    menu_items: List["MenuItem"] = Relationship(back_populates="restaurant")
    ingredients: List["Ingredient"] = Relationship(back_populates="restaurant")
    orders: List["Order"] = Relationship(back_populates="restaurant")
    waste_records: List['FoodWasteRecord'] = Relationship(back_populates="restaurant")
