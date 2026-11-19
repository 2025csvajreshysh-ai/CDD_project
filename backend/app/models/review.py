from datetime import datetime
from typing import Optional, ClassVar
from sqlmodel import SQLModel, Field, Relationship
from app.models.common import utc_now

class Review(SQLModel, table=True):
    __tablename__: ClassVar[str] = "reviews"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="users.id", index=True)
    restaurant_id: int = Field(foreign_key="restaurants.id", index=True)
    menu_item_id: Optional[int] = Field(default=None, foreign_key="menu_items.id")
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
    rating: float = Field(default=5.0)
    comment: str = Field(max_length=500)
    customer_name: Optional[str] = Field(default="Happy Customer", max_length=100)
    created_at: datetime = Field(default_factory=utc_now)

class Favorite(SQLModel, table=True):
    __tablename__: ClassVar[str] = "favorites"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="users.id", index=True)
    restaurant_id: Optional[int] = Field(default=None, foreign_key="restaurants.id")
    menu_item_id: Optional[int] = Field(default=None, foreign_key="menu_items.id")
    created_at: datetime = Field(default_factory=utc_now)
