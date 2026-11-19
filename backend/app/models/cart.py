from datetime import datetime
from typing import ClassVar, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.common import utc_now

if TYPE_CHECKING:
    from app.models.menu import MenuItem

class CartItem(SQLModel, table=True):
    __tablename__: ClassVar[str] = "cart_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="users.id", index=True)
    menu_item_id: int = Field(foreign_key="menu_items.id", index=True)
    quantity: int = Field(default=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    
    menu_item: Optional["MenuItem"] = Relationship()
