from typing import Optional, List, ClassVar, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.models.menu import MenuItem

class Category(SQLModel, table=True):
    __tablename__: ClassVar[str] = "categories"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=100)
    slug: str = Field(unique=True, index=True, max_length=100)
    description: Optional[str] = Field(default=None, max_length=255)
    icon_emoji: Optional[str] = Field(default="🍽️", max_length=10)
    image_url: Optional[str] = Field(default=None, max_length=500)
    display_order: int = Field(default=0)
    
    menu_items: List["MenuItem"] = Relationship(back_populates="category")
