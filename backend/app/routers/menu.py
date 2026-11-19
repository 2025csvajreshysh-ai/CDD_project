from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.menu import MenuItem
from app.models.restaurant import Restaurant
from app.models.category import Category
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.menu import MenuItemCreate, MenuItemUpdate
from app.services.auth_service import get_current_user, require_role

router = APIRouter(prefix="/api/menu", tags=["Menu"])


def _require_menu_item_access(item: MenuItem, current_user: User, session: Session) -> None:
    restaurant = session.get(Restaurant, item.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.KITCHEN_STAFF) and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage menu items for your own restaurants")

@router.get("")
def list_menu_items(
    restaurant_id: Optional[int] = None,
    category_id: Optional[int] = None,
    is_veg: Optional[bool] = None,
    max_price: Optional[float] = None,
    allergen_free: Optional[str] = None,
    search: Optional[str] = None,
    bestseller_only: Optional[bool] = None,
    session: Session = Depends(get_session)
):
    query = select(MenuItem)
    
    if restaurant_id:
        query = query.where(MenuItem.restaurant_id == restaurant_id)
    if category_id:
        query = query.where(MenuItem.category_id == category_id)
    if is_veg is not None:
        query = query.where(MenuItem.is_veg == is_veg)
    if bestseller_only:
        query = query.where(MenuItem.is_bestseller == True)
        
    items = session.exec(query).all()
    
    if max_price is not None:
        items = [i for i in items if (i.discount_price or i.price) <= max_price]
        
    if allergen_free:
        allergen_term = allergen_free.strip().lower()
        items = [
            i for i in items
            if not i.allergens or allergen_term not in i.allergens.lower()
        ]
        
    if search:
        s_term = search.strip().lower()
        items = [
            i for i in items
            if s_term in i.name.lower() or
               s_term in i.description.lower() or
               s_term in i.ingredients.lower()
        ]
        
    return items

@router.get("/{item_id}")
def get_menu_item(item_id: int, session: Session = Depends(get_session)):
    item = session.exec(select(MenuItem).where(MenuItem.id == item_id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")
    return item

@router.get("/restaurant/{restaurant_id}")
def get_restaurant_menu(restaurant_id: int, session: Session = Depends(get_session)):
    items = session.exec(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)
    ).all()
    return items

@router.post("/item", status_code=status.HTTP_201_CREATED)
def create_menu_item(
    item_in: MenuItemCreate,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant = session.get(Restaurant, item_in.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.KITCHEN_STAFF) and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage menu items for your own restaurants")
    if not session.get(Category, item_in.category_id):
        raise HTTPException(status_code=404, detail="Category not found")
    new_item = MenuItem(
        restaurant_id=item_in.restaurant_id,
        category_id=item_in.category_id,
        name=item_in.name,
        description=item_in.description,
        image_url=item_in.image_url,
        price=item_in.price,
        discount_price=item_in.discount_price,
        is_veg=item_in.is_veg,
        prep_time_minutes=item_in.prep_time_minutes,
        ingredients=item_in.ingredients,
        allergens=item_in.allergens,
        is_available=item_in.is_available,
        spice_level=item_in.spice_level,
        dietary_tags=item_in.dietary_tags
    )
    session.add(new_item)
    session.commit()
    session.refresh(new_item)
    return new_item

@router.put("/item/{item_id}")
def update_menu_item(
    item_id: int,
    item_update: MenuItemUpdate,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    item = session.exec(select(MenuItem).where(MenuItem.id == item_id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")
    _require_menu_item_access(item, current_user, session)

    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@router.patch("/item/{item_id}/toggle-availability")
def toggle_item_availability(
    item_id: int,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN, UserRole.KITCHEN_STAFF])),
    session: Session = Depends(get_session)
):
    item = session.exec(select(MenuItem).where(MenuItem.id == item_id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")
    _require_menu_item_access(item, current_user, session)

    item.is_available = not item.is_available
    session.add(item)
    session.commit()
    session.refresh(item)
    return {
        "item_id": item.id,
        "name": item.name,
        "is_available": item.is_available,
        "message": f"{item.name} is now {'Available' if item.is_available else 'Out of Stock'}"
    }

@router.delete("/item/{item_id}")
def delete_menu_item(
    item_id: int,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    item = session.exec(select(MenuItem).where(MenuItem.id == item_id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Food item not found")
    _require_menu_item_access(item, current_user, session)

    # Keep historical order/cart foreign keys valid while removing it from sale.
    item.is_available = False
    session.add(item)
    session.commit()
    return {"message": "Food item successfully deleted"}
