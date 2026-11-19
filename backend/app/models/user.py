from datetime import datetime
from typing import Optional, List, ClassVar
from sqlmodel import SQLModel, Field, Relationship
from app.models.enums import UserRole
from app.models.common import utc_now

class User(SQLModel, table=True):
    __tablename__: ClassVar[str] = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=120)
    hashed_password: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    role: UserRole = Field(default=UserRole.CUSTOMER, index=True)
    is_active: bool = Field(default=True)
    loyalty_points: int = Field(default=100)
    created_at: datetime = Field(default_factory=utc_now)
    
    # Relationships
    preferences: Optional["CustomerPreference"] = Relationship(back_populates="user")
    addresses: List["Address"] = Relationship(back_populates="user")
    notifications: List["Notification"] = Relationship(back_populates="user")

class CustomerPreference(SQLModel, table=True):
    __tablename__: ClassVar[str] = "customer_preferences"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    dietary_preference: str = Field(default="Any")  # Veg, Non-Veg, Vegan, Jain
    allergy_info: Optional[str] = Field(default=None)  # e.g., Peanuts, Dairy, Gluten
    spice_level: str = Field(default="Medium")  # Mild, Medium, Spicy
    favorite_cuisine: Optional[str] = Field(default="South Indian")
    updated_at: datetime = Field(default_factory=utc_now)
    
    user: Optional[User] = Relationship(back_populates="preferences")

class Address(SQLModel, table=True):
    __tablename__: ClassVar[str] = "addresses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    label: str = Field(default="Home", max_length=50)  # Home, Work, Other
    street_address: str = Field(max_length=255)
    city: str = Field(default="Bangalore", max_length=100)
    postal_code: str = Field(default="560001", max_length=20)
    landmark: Optional[str] = Field(default=None, max_length=100)
    latitude: float = Field(default=12.9716)
    longitude: float = Field(default=77.5946)
    is_default: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
    
    user: Optional[User] = Relationship(back_populates="addresses")

class Notification(SQLModel, table=True):
    __tablename__: ClassVar[str] = "notifications"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=120)
    message: str = Field(max_length=500)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
    
    user: Optional[User] = Relationship(back_populates="notifications")
