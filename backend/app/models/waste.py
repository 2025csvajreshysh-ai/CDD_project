from datetime import datetime, date
from typing import Optional, ClassVar, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.common import utc_now

if TYPE_CHECKING:
    from app.models.restaurant import Restaurant

class FoodWasteRecord(SQLModel, table=True):
    __tablename__: ClassVar[str] = "food_waste_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurants.id", index=True)
    ingredient_id: Optional[int] = Field(default=None, foreign_key="ingredients.id")
    ingredient_name: str = Field(max_length=120)
    quantity_wasted: float = Field(default=1.0)
    unit: str = Field(default="kg", max_length=20)
    reason: str = Field(default="Expired", max_length=150)
    estimated_loss_amount: float = Field(default=0.0)
    prevention_recommendation: Optional[str] = Field(default=None, max_length=300)
    recorded_at: datetime = Field(default_factory=utc_now)
    
    restaurant: Optional["Restaurant"] = Relationship(back_populates="waste_records")
