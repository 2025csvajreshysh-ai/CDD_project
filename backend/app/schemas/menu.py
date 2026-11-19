from typing import Optional, List
from pydantic import BaseModel

class MenuItemCreate(BaseModel):
    restaurant_id: int
    category_id: int
    name: str
    description: str
    image_url: str
    price: float
    discount_price: Optional[float] = None
    is_veg: bool = True
    prep_time_minutes: int = 15
    ingredients: str = ""
    allergens: Optional[str] = None
    is_available: bool = True
    spice_level: str = "Medium"
    dietary_tags: Optional[str] = "Vegetarian"

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    discount_price: Optional[float] = None
    is_veg: Optional[bool] = None
    prep_time_minutes: Optional[int] = None
    ingredients: Optional[str] = None
    allergens: Optional[str] = None
    is_available: Optional[bool] = None
    spice_level: Optional[str] = None
    dietary_tags: Optional[str] = None

class IngredientCreate(BaseModel):
    restaurant_id: int
    name: str
    category: str = "Produce"
    unit: str = "kg"
    current_stock: float
    reorder_level: float = 5.0
    cost_per_unit: float = 50.0

class IngredientUpdate(BaseModel):
    current_stock: Optional[float] = None
    reorder_level: Optional[float] = None
    cost_per_unit: Optional[float] = None
