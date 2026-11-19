from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field as SchemaField
from sqlmodel import Session, select, func, col

from app.database import get_session
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.menu import MenuItem
from app.models.inventory import Ingredient, InventoryTransaction
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.waste import FoodWasteRecord
from app.models.enums import OrderStatus, UserRole, InventoryAction
from app.models.common import utc_now
from app.services.auth_service import require_role
from app.algorithms.smart_inventory import get_inventory_and_waste_analysis
from app.websocket.manager import manager
from app.services.access_control import get_restaurant_scope

router = APIRouter(prefix="/api/admin", tags=["Restaurant Admin"])


class RestaurantCreate(BaseModel):
    name: str = SchemaField(min_length=2, max_length=120)
    description: str = SchemaField(min_length=2, max_length=1000)
    address: str = SchemaField(min_length=2, max_length=255)
    image_url: str = SchemaField(min_length=1, max_length=500)
    tagline: Optional[str] = None
    cuisine_type: str = "Multi-Cuisine"
    city: str = "Bangalore"
    phone: str = "+91 98765 43210"
    is_pure_veg: bool = False
    delivery_time_mins: int = SchemaField(default=30, ge=1, le=240)
    cost_for_two: float = SchemaField(default=300, ge=0)
    latitude: float = SchemaField(default=12.9716, ge=-90, le=90)
    longitude: float = SchemaField(default=77.5946, ge=-180, le=180)


class RestaurantUpdate(BaseModel):
    name: Optional[str] = SchemaField(default=None, min_length=2, max_length=120)
    description: Optional[str] = SchemaField(default=None, min_length=2, max_length=1000)
    address: Optional[str] = SchemaField(default=None, min_length=2, max_length=255)
    image_url: Optional[str] = SchemaField(default=None, min_length=1, max_length=500)
    tagline: Optional[str] = None
    cuisine_type: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    is_pure_veg: Optional[bool] = None
    delivery_time_mins: Optional[int] = SchemaField(default=None, ge=1, le=240)
    cost_for_two: Optional[float] = SchemaField(default=None, ge=0)
    latitude: Optional[float] = SchemaField(default=None, ge=-90, le=90)
    longitude: Optional[float] = SchemaField(default=None, ge=-180, le=180)


def _managed_restaurant_or_404(restaurant_id: int, current_user: User, session: Session) -> Restaurant:
    restaurant = session.get(Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if current_user.role != UserRole.SUPER_ADMIN and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage your own restaurants")
    return restaurant


@router.get("/restaurants")
def list_managed_restaurants(
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    query = select(Restaurant).order_by(col(Restaurant.name).asc())
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(Restaurant.owner_id == current_user.id)
    return session.exec(query).all()


@router.post("/restaurants", status_code=201)
def create_restaurant(
    restaurant_in: RestaurantCreate,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant = Restaurant(**restaurant_in.model_dump(), owner_id=current_user.id)
    session.add(restaurant)
    session.commit()
    session.refresh(restaurant)
    return restaurant


@router.put("/restaurants/{restaurant_id}")
def update_restaurant(
    restaurant_id: int,
    restaurant_in: RestaurantUpdate,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant = _managed_restaurant_or_404(restaurant_id, current_user, session)
    for field, value in restaurant_in.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    session.add(restaurant)
    session.commit()
    session.refresh(restaurant)
    return restaurant

@router.get("/dashboard-stats")
def get_dashboard_stats(
    restaurant_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant_scope = get_restaurant_scope(session, current_user, restaurant_id)
    order_query = select(Order)
    if restaurant_scope is not None:
        order_query = order_query.where(col(Order.restaurant_id).in_(restaurant_scope))
    orders = session.exec(order_query).all()

    total_orders = len(orders)
    total_revenue = sum(o.total_amount for o in orders if o.status != OrderStatus.CANCELLED)
    active_orders = len([o for o in orders if o.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY]])

    menu_query = select(MenuItem)
    if restaurant_scope is not None:
        menu_query = menu_query.where(col(MenuItem.restaurant_id).in_(restaurant_scope))
    menu_items = session.exec(menu_query).all()
    total_menu_items = len(menu_items)

    ing_query = select(Ingredient)
    if restaurant_scope is not None:
        ing_query = ing_query.where(col(Ingredient.restaurant_id).in_(restaurant_scope))
    ingredients = session.exec(ing_query).all()
    low_stock_count = len([i for i in ingredients if i.current_stock <= i.reorder_level])

    unique_customer_ids = {o.customer_id for o in orders}
    customer_count = len(unique_customer_ids)

    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "active_orders": active_orders,
        "total_menu_items": total_menu_items,
        "low_stock_items": low_stock_count,
        "customer_count": max(customer_count, 1)
    }

@router.get("/analytics/revenue")
def get_revenue_analytics(
    restaurant_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant_scope = get_restaurant_scope(session, current_user, restaurant_id)
    order_query = select(Order).where(Order.status != OrderStatus.CANCELLED)
    if restaurant_scope is not None:
        order_query = order_query.where(col(Order.restaurant_id).in_(restaurant_scope))
    orders = session.exec(order_query).all()

    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    daily_totals = {day: 0.0 for day in days}
    current_week = today - timedelta(days=today.weekday())
    weeks = [current_week - timedelta(weeks=offset) for offset in range(3, -1, -1)]
    weekly_totals = {week: 0.0 for week in weeks}
    months = []
    year, month = today.year, today.month
    for offset in range(5, -1, -1):
        target_month = month - offset
        target_year = year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        months.append((target_year, target_month))
    monthly_totals = {month_key: 0.0 for month_key in months}

    for order in orders:
        created_at = order.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        order_day = created_at.astimezone(timezone.utc).date()
        if order_day in daily_totals:
            daily_totals[order_day] += order.total_amount
        week_start = order_day - timedelta(days=order_day.weekday())
        if week_start in weekly_totals:
            weekly_totals[week_start] += order.total_amount
        month_key = (order_day.year, order_day.month)
        if month_key in monthly_totals:
            monthly_totals[month_key] += order.total_amount

    daily_labels = [day.strftime("%a (%b %d)") for day in days]
    daily_values = [round(daily_totals[day], 2) for day in days]
    weekly_labels = [week.strftime("Week of %b %d") for week in weeks]
    weekly_values = [round(weekly_totals[week], 2) for week in weeks]
    monthly_labels = [datetime(month_year, month_number, 1).strftime("%b %Y") for month_year, month_number in months]
    monthly_values = [round(monthly_totals[month_key], 2) for month_key in months]

    return {
        "daily": {"labels": daily_labels, "data": daily_values},
        "weekly": {"labels": weekly_labels, "data": weekly_values},
        "monthly": {"labels": monthly_labels, "data": monthly_values}
    }

@router.get("/analytics/peak-hours")
def get_peak_hours(
    restaurant_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant_scope = get_restaurant_scope(session, current_user, restaurant_id)
    order_query = select(Order)
    if restaurant_scope is not None:
        order_query = order_query.where(col(Order.restaurant_id).in_(restaurant_scope))
    orders = session.exec(order_query).all()

    hour_counts = {h: 0 for h in range(24)}
    for o in orders:
        h = o.created_at.hour
        hour_counts[h] += 1

    labels = [f"{h:02d}:00" for h in range(24)]
    data = [hour_counts[h] for h in range(24)]

    return {"labels": labels, "data": data}

@router.get("/analytics/bestsellers")
def get_bestsellers_analytics(
    restaurant_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant_scope = get_restaurant_scope(session, current_user, restaurant_id)
    menu_query = select(MenuItem)
    if restaurant_scope is not None:
        menu_query = menu_query.where(col(MenuItem.restaurant_id).in_(restaurant_scope))
    items = session.exec(menu_query).all()
    order_query = select(Order.id).where(Order.status != OrderStatus.CANCELLED)
    if restaurant_scope is not None:
        order_query = order_query.where(col(Order.restaurant_id).in_(restaurant_scope))
    order_ids = session.exec(order_query).all()
    quantities: dict[int, int] = {}
    revenues: dict[int, float] = {}
    if order_ids:
        for order_item in session.exec(select(OrderItem).where(col(OrderItem.order_id).in_(order_ids))).all():
            quantities[order_item.menu_item_id] = quantities.get(order_item.menu_item_id, 0) + order_item.quantity
            revenues[order_item.menu_item_id] = revenues.get(order_item.menu_item_id, 0.0) + order_item.total_price
    items.sort(key=lambda item: (quantities.get(item.id, 0), item.rating), reverse=True)
    top_items = [item for item in items if quantities.get(item.id, 0) > 0][:7]

    return {
        "labels": [i.name for i in top_items],
        "order_counts": [quantities[item.id] for item in top_items],
        "revenues": [round(revenues.get(item.id, 0.0), 2) for item in top_items]
    }

@router.get("/orders")
def get_admin_orders(
    restaurant_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant_scope = get_restaurant_scope(session, current_user, restaurant_id)
    query = select(Order).order_by(col(Order.created_at).desc())
    if restaurant_scope is not None:
        query = query.where(col(Order.restaurant_id).in_(restaurant_scope))
    if status_filter and status_filter.lower() != "all":
        query = query.where(Order.status == status_filter)

    orders = session.exec(query).all()
    results = []
    for o in orders:
        items = session.exec(select(OrderItem).where(OrderItem.order_id == o.id)).all()
        cust = session.exec(select(User).where(User.id == o.customer_id)).first()
        results.append({
            "id": o.id,
            "order_number": o.order_number,
            "customer_name": cust.full_name if cust else "Customer",
            "customer_phone": cust.phone if cust else "",
            "status": o.status.value,
            "total_amount": o.total_amount,
            "payment_method": o.payment_method.value,
            "payment_status": o.payment_status.value,
            "items_count": len(items),
            "items": [{"name": i.item_name, "quantity": i.quantity, "price": i.total_price} for i in items],
            "delivery_address": o.delivery_address,
            "created_at": o.created_at.strftime("%I:%M %p, %b %d"),
            "priority_score": o.priority_score
        })
    return results

@router.get("/inventory")
def get_inventory_list(
    restaurant_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    restaurant_scope = get_restaurant_scope(session, current_user, restaurant_id)
    if restaurant_scope is None:
        return get_inventory_and_waste_analysis(session, restaurant_id)

    reports = [get_inventory_and_waste_analysis(session, owned_id) for owned_id in restaurant_scope]
    return {
        "total_ingredients_monitored": sum(r["total_ingredients_monitored"] for r in reports),
        "total_inventory_value": round(sum(r["total_inventory_value"] for r in reports), 2),
        "low_stock_alerts_count": sum(r["low_stock_alerts_count"] for r in reports),
        "low_stock_alerts": [item for r in reports for item in r["low_stock_alerts"]],
        "expiry_warnings_count": sum(r["expiry_warnings_count"] for r in reports),
        "expiry_warnings": [item for r in reports for item in r["expiry_warnings"]],
        "total_waste_loss_amount": round(sum(r["total_waste_loss_amount"] for r in reports), 2),
        "waste_records_count": sum(r["waste_records_count"] for r in reports),
        "recent_waste_logs": [item for r in reports for item in r["recent_waste_logs"]][-8:],
    }

@router.post("/inventory/restock")
def restock_ingredient(
    ingredient_id: int = Query(gt=0),
    quantity_to_add: float = Query(gt=0, le=100000),
    current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    ing = session.exec(select(Ingredient).where(Ingredient.id == ingredient_id)).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    get_restaurant_scope(session, current_user, ing.restaurant_id)

    ing.current_stock += quantity_to_add
    ing.is_low_stock = ing.current_stock <= ing.reorder_level
    ing.updated_at = utc_now()
    session.add(ing)

    tx = InventoryTransaction(
        ingredient_id=ing.id,
        restaurant_id=ing.restaurant_id,
        action=InventoryAction.STOCK_IN,
        quantity_changed=quantity_to_add,
        balance_after=ing.current_stock,
        notes=f"Stock replenishment +{quantity_to_add} {ing.unit}",
        created_at=utc_now()
    )
    session.add(tx)
    session.commit()
    return {"message": f"Successfully restocked {ing.name}. New balance: {ing.current_stock} {ing.unit}"}
