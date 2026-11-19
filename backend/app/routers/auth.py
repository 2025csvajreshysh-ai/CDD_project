from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User, CustomerPreference, Address
from app.models.enums import UserRole
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserOut,
    DemoLoginRequest
)
from app.services.auth_service import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Defined demo accounts mapping as requested in Section 7
DEMO_CREDENTIALS = {
    UserRole.CUSTOMER: "customer@demo.com",
    UserRole.RESTAURANT_ADMIN: "admin@demo.com",
    UserRole.KITCHEN_STAFF: "kitchen@demo.com",
    UserRole.DELIVERY_PARTNER: "delivery@demo.com",
    UserRole.SUPER_ADMIN: "superadmin@demo.com"
}

@router.post("/register", response_model=TokenResponse)
def register(user_in: UserRegister, session: Session = Depends(get_session)):
    if user_in.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Public registration is limited to customer accounts")
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        full_name=user_in.full_name,
        phone=user_in.phone,
        role=UserRole.CUSTOMER,
        is_active=True,
        loyalty_points=100
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # Create default customer preferences & demo address
    pref = CustomerPreference(
        user_id=new_user.id,
        dietary_preference="Any",
        spice_level="Medium",
        favorite_cuisine="South Indian"
    )
    session.add(pref)
    addr = Address(
        user_id=new_user.id,
        label="Home",
        street_address="12, Koramangala 4th Block",
        city="Bangalore",
        postal_code="560034",
        landmark="Near Sony World Signal",
        is_default=True
    )
    session.add(addr)
    session.commit()

    token = create_access_token({"sub": new_user.email, "role": new_user.role.value, "uid": new_user.id})
    return TokenResponse(
        access_token=token,
        user_id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        role=new_user.role
    )

@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == login_data.email)).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact super admin."
        )

    token = create_access_token({"sub": user.email, "role": user.role.value, "uid": user.id})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role
    )

@router.post("/demo-login", response_model=TokenResponse)
def demo_login(req: DemoLoginRequest, session: Session = Depends(get_session)):
    """
    Dedicated One-Click Demo Login for all 5 roles:
    Customer, Restaurant Admin, Kitchen Staff, Delivery Partner, Super Admin.
    """
    target_email = DEMO_CREDENTIALS.get(req.role)
    if not target_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid demo role requested."
        )

    user = session.exec(select(User).where(User.email == target_email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo user for role '{req.role.value}' not found in database. Run database seed."
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This demo account has been deactivated")

    token = create_access_token({"sub": user.email, "role": user.role.value, "uid": user.id})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role
    )

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        role=current_user.role,
        is_active=current_user.is_active,
        loyalty_points=current_user.loyalty_points
    )
