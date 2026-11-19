from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.cart import CartItem
from app.models.menu import MenuItem
from app.models.restaurant import Restaurant
from app.models.user import User
from app.models.common import utc_now
from app.schemas.order import CartItemAdd, CartItemUpdate, CouponApply
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/cart", tags=["Shopping Cart"])

COUPONS = {
    "AIFOODIE20": {"type": "percent", "discount": 20, "max_discount": 100, "min_order": 199},
    "WELCOME50": {"type": "flat", "discount": 50, "max_discount": 50, "min_order": 149},
    "FEAST10": {"type": "percent", "discount": 10, "max_discount": 200, "min_order": 299},
    "DEMO100": {"type": "flat", "discount": 100, "max_discount": 100, "min_order": 300}
}

@router.get("")
def get_cart(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    cart_items = session.exec(
        select(CartItem).where(CartItem.customer_id == current_user.id)
    ).all()
    
    items_data = []
    subtotal = 0.0
    restaurant_id = None
    
    for ci in cart_items:
        menu_item = session.exec(select(MenuItem).where(MenuItem.id == ci.menu_item_id)).first()
        if menu_item and menu_item.is_available:
            item_price = menu_item.discount_price or menu_item.price
            total_item_price = item_price * ci.quantity
            subtotal += total_item_price
            restaurant_id = menu_item.restaurant_id
            
            items_data.append({
                "cart_item_id": ci.id,
                "menu_item_id": menu_item.id,
                "name": menu_item.name,
                "price": item_price,
                "quantity": ci.quantity,
                "total_price": total_item_price,
                "image_url": menu_item.image_url,
                "is_veg": menu_item.is_veg,
                "restaurant_id": menu_item.restaurant_id
            })

    tax = round(subtotal * 0.05, 2)
    delivery_fee = 30.0 if subtotal > 0 else 0.0
    final_total = round(subtotal + tax + delivery_fee, 2)

    return {
        "items": items_data,
        "item_count": sum(i["quantity"] for i in items_data),
        "subtotal": round(subtotal, 2),
        "tax": tax,
        "delivery_fee": delivery_fee,
        "total_amount": final_total,
        "restaurant_id": restaurant_id
    }

@router.post("/add")
def add_to_cart(
    item_in: CartItemAdd,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    menu_item = session.exec(select(MenuItem).where(MenuItem.id == item_in.menu_item_id)).first()
    if not menu_item or not menu_item.is_available:
        raise HTTPException(status_code=400, detail="Food item is unavailable")

    # A single checkout can only be fulfilled by one restaurant.
    current_items = session.exec(
        select(CartItem).where(CartItem.customer_id == current_user.id)
    ).all()
    different_restaurant_items = []
    for cart_item in current_items:
        existing_menu_item = session.get(MenuItem, cart_item.menu_item_id)
        if existing_menu_item and existing_menu_item.restaurant_id != menu_item.restaurant_id:
            different_restaurant_items.append((cart_item, existing_menu_item))

    if different_restaurant_items:
        if item_in.replace_cart:
            for ci in current_items:
                session.delete(ci)
            session.commit()
            current_items = []
        else:
            existing_first = different_restaurant_items[0][1]
            existing_rest = session.get(Restaurant, existing_first.restaurant_id)
            new_rest = session.get(Restaurant, menu_item.restaurant_id)
            old_name = existing_rest.name if existing_rest else "another restaurant"
            new_name = new_rest.name if new_rest else "this restaurant"
            raise HTTPException(
                status_code=400,
                detail=f"Your cart already contains items from {old_name}. Discard and add from {new_name}?"
            )

    existing_ci = session.exec(
        select(CartItem)
        .where(CartItem.customer_id == current_user.id)
        .where(CartItem.menu_item_id == item_in.menu_item_id)
    ).first()

    if existing_ci:
        existing_ci.quantity += item_in.quantity
        existing_ci.updated_at = utc_now()
        session.add(existing_ci)
    else:
        new_ci = CartItem(
            customer_id=current_user.id,
            menu_item_id=item_in.menu_item_id,
            quantity=item_in.quantity,
            created_at=utc_now(),
            updated_at=utc_now()
        )
        session.add(new_ci)

    session.commit()
    return {"message": f"Added {menu_item.name} to cart successfully"}

@router.put("/update")
def update_cart_item(
    update_in: CartItemUpdate,
    menu_item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    ci = session.exec(
        select(CartItem)
        .where(CartItem.customer_id == current_user.id)
        .where(CartItem.menu_item_id == menu_item_id)
    ).first()

    if not ci:
        raise HTTPException(status_code=404, detail="Cart item not found")

    if update_in.quantity <= 0:
        session.delete(ci)
    else:
        ci.quantity = update_in.quantity
        ci.updated_at = utc_now()
        session.add(ci)

    session.commit()
    return {"message": "Cart updated"}

@router.delete("/remove/{menu_item_id}")
def remove_from_cart(
    menu_item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    ci = session.exec(
        select(CartItem)
        .where(CartItem.customer_id == current_user.id)
        .where(CartItem.menu_item_id == menu_item_id)
    ).first()

    if ci:
        session.delete(ci)
        session.commit()

    return {"message": "Item removed from cart"}

@router.delete("/clear")
def clear_cart(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    items = session.exec(
        select(CartItem).where(CartItem.customer_id == current_user.id)
    ).all()
    for item in items:
        session.delete(item)
    session.commit()
    return {"message": "Cart cleared"}

@router.post("/validate-coupon")
def validate_coupon(coupon_in: CouponApply):
    code = coupon_in.code.strip().upper()
    rule = COUPONS.get(code)
    if not rule:
        raise HTTPException(status_code=400, detail="Invalid coupon code. Try AIFOODIE20 or WELCOME50.")

    if coupon_in.subtotal < rule["min_order"]:
        raise HTTPException(
            status_code=400,
            detail=f"Coupon requires a minimum order subtotal of ₹{rule['min_order']}."
        )

    if rule["type"] == "percent":
        discount = round(coupon_in.subtotal * (rule["discount"] / 100.0), 2)
        discount = min(discount, rule["max_discount"])
    else:
        discount = float(rule["discount"])

    return {
        "valid": True,
        "coupon_code": code,
        "discount_amount": discount,
        "message": f"Coupon applied! You saved ₹{discount:.2f}."
    }
