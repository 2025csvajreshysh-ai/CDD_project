from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select, col

from app.database import get_session
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.restaurant import Restaurant
from app.models.delivery import DeliveryProfile
from app.models.enums import OrderStatus, UserRole
from app.models.common import utc_now
from app.services.auth_service import require_role
from app.websocket.manager import manager
from app.algorithms.delivery_dispatch import haversine_distance_km
from app.services.geo_service import assign_nearest_available_partner, calculate_eta_minutes
from app.services.auth_service import get_current_user, decode_access_token
from app.database import engine
from app.websocket.delivery_manager import delivery_manager

router = APIRouter(prefix="/api/delivery", tags=["Delivery Partner"])

@router.patch("/availability")
def set_partner_availability(is_available: bool, current_user: User = Depends(require_role([UserRole.DELIVERY_PARTNER])), session: Session = Depends(get_session)):
    profile = session.exec(select(DeliveryProfile).where(DeliveryProfile.user_id == current_user.id)).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Delivery partner profile not found")
    profile.is_available = is_available
    profile.last_location_updated = utc_now()
    session.add(profile)
    session.commit()
    return {"is_available": profile.is_available}

@router.post("/orders/{order_id}/assign")
def dispatch_order(order_id: int, current_user: User = Depends(require_role([UserRole.RESTAURANT_ADMIN, UserRole.SUPER_ADMIN, UserRole.KITCHEN_STAFF])), session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in (OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY):
        raise HTTPException(status_code=409, detail="Only confirmed orders can be dispatched")
    restaurant = session.get(Restaurant, order.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=409, detail="Restaurant location is unavailable")
    if current_user.role == UserRole.RESTAURANT_ADMIN and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not manage this restaurant")
    if order.delivery_partner_id:
        existing_partner = session.get(User, order.delivery_partner_id)
        return {"order_id": order.id, "delivery_partner_id": order.delivery_partner_id,
                "partner_name": existing_partner.full_name if existing_partner else None}
    partner = assign_nearest_available_partner(session, order, restaurant.latitude, restaurant.longitude)
    if not partner:
        raise HTTPException(status_code=409, detail="No available delivery partner")
    order.delivery_partner_id = partner.id
    session.add(order)
    session.commit()
    return {"order_id": order.id, "delivery_partner_id": partner.id, "partner_name": partner.full_name}

@router.get("/orders/{order_id}/eta")
def order_eta(order_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    restaurant = session.get(Restaurant, order.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=409, detail="Restaurant location is unavailable")
    can_view = current_user.id in (order.customer_id, order.delivery_partner_id) or current_user.role in (UserRole.KITCHEN_STAFF, UserRole.SUPER_ADMIN)
    if not can_view:
        raise HTTPException(status_code=403, detail="You do not have access to this order")
    distance = haversine_distance_km(restaurant.latitude, restaurant.longitude, order.delivery_latitude, order.delivery_longitude)
    remaining_prep = order.estimated_prep_minutes if order.status in (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PREPARING) else 0
    if order.status == OrderStatus.PREPARING:
        started = session.exec(select(OrderStatusHistory).where(
            OrderStatusHistory.order_id == order.id,
            OrderStatusHistory.status == OrderStatus.PREPARING,
        ).order_by(col(OrderStatusHistory.timestamp).desc())).first()
        if started:
            started_at = started.timestamp
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            elapsed = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds() // 60))
            remaining_prep = max(0, remaining_prep - elapsed)
    eta = calculate_eta_minutes(distance, remaining_prep)
    return {"order_id": order.id, "distance_km": round(distance, 2), "remaining_prep_minutes": remaining_prep, "travel_speed_kmh": 25, "buffer_minutes": 5, "eta_minutes": eta}

@router.get("/orders/{order_id}/location")
def order_location(order_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.id not in (order.customer_id, order.delivery_partner_id) and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="You do not have access to this order")
    restaurant = session.get(Restaurant, order.restaurant_id)
    profile = session.exec(select(DeliveryProfile).where(DeliveryProfile.user_id == order.delivery_partner_id)).first() if order.delivery_partner_id else None
    return {"order_id": order.id, "restaurant": {"lat": restaurant.latitude, "lon": restaurant.longitude} if restaurant else None,
            "customer": {"lat": order.delivery_latitude, "lon": order.delivery_longitude},
            "partner": {"lat": profile.current_latitude, "lon": profile.current_longitude} if profile else None}

async def delivery_tracking_websocket(websocket: WebSocket, order_id: int, token: str):
    """Rider sends {lat, lon}; customer receives location events for this order."""
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=4401)
        return
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == payload["sub"])).first()
        order = db.get(Order, order_id)
        if not user or not user.is_active or not order or (user.id not in (order.customer_id, order.delivery_partner_id) and user.role != UserRole.SUPER_ADMIN):
            await websocket.close(code=4403)
            return
        role = "partner" if user.id == order.delivery_partner_id else "customer"
    await delivery_manager.connect(order_id, role, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if role != "partner":
                await websocket.send_json({"type": "error", "detail": "Only the assigned delivery partner may publish locations"})
                continue
            try:
                lat, lon = float(data["lat"]), float(data["lon"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                await websocket.send_json({"type": "error", "detail": "Expected valid lat and lon coordinates"})
                continue
            with Session(engine) as db:
                profile = db.exec(select(DeliveryProfile).where(DeliveryProfile.user_id == user.id)).first()
                if profile:
                    profile.current_latitude, profile.current_longitude = lat, lon
                    profile.last_location_updated = utc_now()
                    db.add(profile)
                    db.commit()
            await delivery_manager.broadcast(order_id, {"type": "location", "order_id": order_id, "lat": lat, "lon": lon, "timestamp": utc_now().isoformat()})
    except WebSocketDisconnect:
        delivery_manager.disconnect(order_id, websocket)

@router.get("/assigned-orders")
def get_assigned_orders(
    partner_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.DELIVERY_PARTNER, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    query = select(Order).where(
        col(Order.status).in_([OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY])
    )
    if current_user.role == UserRole.DELIVERY_PARTNER:
        partner_id = current_user.id
    if partner_id:
        query = query.where(Order.delivery_partner_id == partner_id)

    orders = session.exec(query.order_by(col(Order.created_at).desc())).all()

    results = []
    for o in orders:
        rest = session.exec(select(Restaurant).where(Restaurant.id == o.restaurant_id)).first()
        cust = session.exec(select(User).where(User.id == o.customer_id)).first()
        items = session.exec(select(OrderItem).where(OrderItem.order_id == o.id)).all()

        results.append({
            "order_id": o.id,
            "order_number": o.order_number,
            "status": o.status.value,
            "restaurant_name": rest.name if rest else "Spice Garden",
            "restaurant_address": rest.address if rest else "Indiranagar, Bangalore",
            "restaurant_lat": rest.latitude if rest else 12.9716,
            "restaurant_lon": rest.longitude if rest else 77.5946,
            "customer_name": cust.full_name if cust else "Customer",
            "customer_phone": cust.phone if cust else "+91 98765 00000",
            "delivery_address": o.delivery_address,
            "delivery_lat": o.delivery_latitude,
            "delivery_lon": o.delivery_longitude,
            "total_amount": o.total_amount,
            "delivery_fee_earning": o.delivery_fee + 15.0,
            "items_count": len(items),
            "estimated_delivery_minutes": o.estimated_delivery_minutes,
            "customer_notes": o.customer_notes
        })

    return results

@router.post("/orders/{order_id}/action")
async def update_delivery_action(
    order_id: int,
    action: str,
    current_user: User = Depends(require_role([UserRole.DELIVERY_PARTNER, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    order = session.exec(select(Order).where(Order.id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.DELIVERY_PARTNER and order.delivery_partner_id != current_user.id:
        raise HTTPException(status_code=403, detail="This delivery is assigned to another partner")

    action_map = {
        "picked_up": OrderStatus.OUT_FOR_DELIVERY,
        "out_for_delivery": OrderStatus.OUT_FOR_DELIVERY,
        "delivered": OrderStatus.DELIVERED
    }

    target_status = action_map.get(action.lower())
    if not target_status:
        raise HTTPException(status_code=400, detail=f"Invalid delivery action '{action}'")

    allowed_source_statuses = {
        OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.READY},
        OrderStatus.DELIVERED: {OrderStatus.OUT_FOR_DELIVERY},
    }
    if order.status not in allowed_source_statuses[target_status]:
        expected = "ready for pickup" if target_status == OrderStatus.OUT_FOR_DELIVERY else "out for delivery"
        raise HTTPException(status_code=409, detail=f"Order must be {expected} before this delivery update")

    order.status = target_status
    order.updated_at = utc_now()
    session.add(order)

    if target_status == OrderStatus.DELIVERED and order.delivery_partner_id:
        profile = session.exec(
            select(DeliveryProfile).where(DeliveryProfile.user_id == order.delivery_partner_id)
        ).first()
        if profile:
            profile.total_deliveries += 1
            profile.total_earnings += (order.delivery_fee + 15.0)
            session.add(profile)

    history = OrderStatusHistory(
        order_id=order.id,
        status=target_status,
        notes=f"Delivery update: {action.replace('_', ' ').title()}",
        changed_by_role=current_user.role.value,
        timestamp=utc_now()
    )
    session.add(history)
    session.commit()

    await manager.broadcast(
        {
            "event": "DELIVERY_STATUS_UPDATED",
            "order_id": order.id,
            "order_number": order.order_number,
            "new_status": target_status.value,
            "action": action,
        },
        restaurant_id=order.restaurant_id,
        user_ids=[order.customer_id, order.delivery_partner_id],
    )

    return {
        "message": f"Order #{order.order_number} updated to {target_status.value}",
        "new_status": target_status.value
    }

@router.get("/stats")
def get_delivery_partner_stats(
    partner_id: Optional[int] = None,
    current_user: User = Depends(require_role([UserRole.DELIVERY_PARTNER, UserRole.SUPER_ADMIN])),
    session: Session = Depends(get_session)
):
    if current_user.role == UserRole.DELIVERY_PARTNER:
        partner_id = current_user.id
    profile = None
    if partner_id:
        profile = session.exec(select(DeliveryProfile).where(DeliveryProfile.user_id == partner_id)).first()
    
    return {
        "total_deliveries": profile.total_deliveries if profile else 0,
        "total_earnings": profile.total_earnings if profile else 0.0,
        "rating": profile.rating if profile else 0.0,
        "vehicle_type": profile.vehicle_type if profile else None,
        "vehicle_number": profile.vehicle_number if profile else None,
        "is_available": profile.is_available if profile else False
    }
