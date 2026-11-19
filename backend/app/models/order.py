from datetime import datetime
from typing import Optional, List, ClassVar, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus
from app.models.common import utc_now

if TYPE_CHECKING:
    from app.models.menu import MenuItem
    from app.models.restaurant import Restaurant

class Order(SQLModel, table=True):
    __tablename__: ClassVar[str] = "orders"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_number: str = Field(unique=True, index=True, max_length=50)
    customer_id: int = Field(foreign_key="users.id", index=True)
    restaurant_id: int = Field(foreign_key="restaurants.id", index=True)
    delivery_partner_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    
    status: OrderStatus = Field(default=OrderStatus.PENDING, index=True)
    
    # Financial amounts
    subtotal: float = Field(default=0.0)
    delivery_fee: float = Field(default=30.0)
    tax: float = Field(default=0.0)
    discount: float = Field(default=0.0)
    total_amount: float = Field(default=0.0)
    coupon_code: Optional[str] = Field(default=None, max_length=50)
    
    # Payment details
    payment_method: PaymentMethod = Field(default=PaymentMethod.COD)
    payment_status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    transaction_id: Optional[str] = Field(default=None, max_length=100)
    
    # Delivery address & coords
    delivery_address: str = Field(max_length=400)
    delivery_latitude: float = Field(default=12.9716)
    delivery_longitude: float = Field(default=77.5946)
    customer_notes: Optional[str] = Field(default=None, max_length=300)
    
    # AI Intelligent kitchen priority & ETA metrics
    priority_score: float = Field(default=1.0)
    estimated_prep_minutes: int = Field(default=20)
    estimated_delivery_minutes: int = Field(default=35)
    
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)
    
    # Relationships
    items: List["OrderItem"] = Relationship(back_populates="order")
    status_history: List["OrderStatusHistory"] = Relationship(back_populates="order")
    restaurant: Optional["Restaurant"] = Relationship(back_populates="orders")
    payments: List["Payment"] = Relationship(back_populates="order")

class OrderItem(SQLModel, table=True):
    __tablename__: ClassVar[str] = "order_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    menu_item_id: int = Field(foreign_key="menu_items.id", index=True)
    item_name: str = Field(max_length=150)
    quantity: int = Field(default=1)
    unit_price: float = Field(default=0.0)
    total_price: float = Field(default=0.0)
    special_instructions: Optional[str] = Field(default=None, max_length=200)
    
    order: Optional[Order] = Relationship(back_populates="items")
    menu_item: Optional["MenuItem"] = Relationship()

class OrderStatusHistory(SQLModel, table=True):
    __tablename__: ClassVar[str] = "order_status_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    status: OrderStatus = Field(index=True)
    notes: Optional[str] = Field(default=None, max_length=255)
    changed_by_role: Optional[str] = Field(default="system", max_length=50)
    timestamp: datetime = Field(default_factory=utc_now)
    
    order: Optional[Order] = Relationship(back_populates="status_history")

class Payment(SQLModel, table=True):
    __tablename__: ClassVar[str] = "payments"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    payment_method: PaymentMethod = Field(default=PaymentMethod.COD)
    amount: float = Field(default=0.0)
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    transaction_ref: Optional[str] = Field(default=None, max_length=100)
    gateway_response: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    
    order: Optional[Order] = Relationship(back_populates="payments")
