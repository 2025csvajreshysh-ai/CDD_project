from datetime import datetime, date
from typing import Optional, List, ClassVar, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.enums import InventoryAction
from app.models.common import utc_now

if TYPE_CHECKING:
    from app.models.menu import RecipeItem
    from app.models.restaurant import Restaurant

class Ingredient(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ingredients"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurants.id", index=True)
    name: str = Field(index=True, max_length=120)
    category: str = Field(default="Produce", max_length=60)
    unit: str = Field(default="kg", max_length=20)
    current_stock: float = Field(default=10.0)
    reorder_level: float = Field(default=5.0)
    cost_per_unit: float = Field(default=50.0)
    expiry_date: Optional[date] = Field(default=None)
    is_low_stock: bool = Field(default=False, index=True)
    updated_at: datetime = Field(default_factory=utc_now)
    
    restaurant: Optional["Restaurant"] = Relationship(back_populates="ingredients")
    recipe_items: List["RecipeItem"] = Relationship(back_populates="ingredient")
    transactions: List["InventoryTransaction"] = Relationship(back_populates="ingredient")

class InventoryTransaction(SQLModel, table=True):
    __tablename__: ClassVar[str] = "inventory_transactions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredients.id", index=True)
    restaurant_id: int = Field(foreign_key="restaurants.id", index=True)
    action: InventoryAction = Field(default=InventoryAction.ORDER_DEDUCTION)
    quantity_changed: float = Field(default=0.0)
    balance_after: float = Field(default=0.0)
    order_id: Optional[int] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now)
    
    ingredient: Optional[Ingredient] = Relationship(back_populates="transactions")
