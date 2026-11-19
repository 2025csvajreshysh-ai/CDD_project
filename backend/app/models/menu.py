from datetime import datetime
from typing import Optional, List, ClassVar, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.common import utc_now

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.inventory import Ingredient
    from app.models.restaurant import Restaurant

class MenuItem(SQLModel, table=True):
    __tablename__: ClassVar[str] = "menu_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(foreign_key="restaurants.id", index=True)
    category_id: int = Field(foreign_key="categories.id", index=True)
    
    name: str = Field(index=True, max_length=150)
    description: str = Field(max_length=600)
    image_url: str = Field(max_length=500)
    price: float = Field(default=0.0)
    discount_price: Optional[float] = Field(default=None)
    
    is_veg: bool = Field(default=True, index=True)
    prep_time_minutes: int = Field(default=15)
    ingredients: str = Field(default="", max_length=500)
    allergens: Optional[str] = Field(default=None, max_length=255)
    is_available: bool = Field(default=True, index=True)
    rating: float = Field(default=4.5)
    total_ratings: int = Field(default=10)
    total_orders_count: int = Field(default=0)
    
    is_bestseller: bool = Field(default=False)
    is_recommended: bool = Field(default=False)
    spice_level: str = Field(default="Medium")
    calories: Optional[int] = Field(default=350)
    dietary_tags: Optional[str] = Field(default="Vegetarian")
    
    created_at: datetime = Field(default_factory=utc_now)
    
    # Relationships
    restaurant: Optional["Restaurant"] = Relationship(back_populates="menu_items")
    category: Optional["Category"] = Relationship(back_populates="menu_items")
    recipe_items: List["RecipeItem"] = Relationship(back_populates="menu_item")

class RecipeItem(SQLModel, table=True):
    __tablename__: ClassVar[str] = "recipe_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    menu_item_id: int = Field(foreign_key="menu_items.id", index=True)
    ingredient_id: int = Field(foreign_key="ingredients.id", index=True)
    quantity_required: float = Field(default=1.0)
    
    menu_item: Optional[MenuItem] = Relationship(back_populates="recipe_items")
    ingredient: Optional["Ingredient"] = Relationship(back_populates="recipe_items")
