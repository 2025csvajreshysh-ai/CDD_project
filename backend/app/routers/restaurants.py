from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, col
from app.database import get_session
from app.models.restaurant import Restaurant
from app.models.category import Category
from app.models.menu import MenuItem

router = APIRouter(prefix="/api/restaurants", tags=["Restaurants"])

@router.get("")
def list_restaurants(
    cuisine: Optional[str] = None,
    pure_veg: Optional[bool] = None,
    search: Optional[str] = None,
    session: Session = Depends(get_session)
):
    query = select(Restaurant).where(Restaurant.is_active == True)
    
    if pure_veg is not None and pure_veg is True:
        query = query.where(Restaurant.is_pure_veg == True)
        
    restaurants = session.exec(query).all()
    
    # Filter by cuisine or search term in Python for flexibility
    if cuisine:
        cuisine_lower = cuisine.lower()
        restaurants = [r for r in restaurants if cuisine_lower in r.cuisine_type.lower()]
        
    if search:
        search_lower = search.lower()
        restaurants = [
            r for r in restaurants
            if search_lower in r.name.lower() or
               search_lower in r.description.lower() or
               search_lower in r.cuisine_type.lower() or
               search_lower in r.city.lower()
        ]
        
    return restaurants

@router.get("/categories/all")
def get_categories(session: Session = Depends(get_session)):
    categories = session.exec(
        select(Category).order_by(col(Category.display_order).asc())
    ).all()
    return categories

@router.get("/{restaurant_id}")
def get_restaurant_details(restaurant_id: int, session: Session = Depends(get_session)):
    restaurant = session.exec(
        select(Restaurant).where(Restaurant.id == restaurant_id)
    ).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
        
    menu_items = session.exec(
        select(MenuItem)
        .where(MenuItem.restaurant_id == restaurant_id)
        .where(MenuItem.is_available == True)
    ).all()
    
    return {
        "restaurant": restaurant,
        "menu_items": menu_items,
        "total_items": len(menu_items)
    }
