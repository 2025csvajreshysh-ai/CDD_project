from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import UserRole

class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    role: UserRole = UserRole.CUSTOMER

class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    full_name: str
    role: UserRole

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    loyalty_points: int

class DemoLoginRequest(BaseModel):
    role: UserRole
