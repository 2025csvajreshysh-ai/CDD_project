from datetime import datetime, timezone
from typing import List, Dict, Any
from app.models.order import Order

def calculate_kitchen_priority_score(order: Order, elapsed_minutes: float) -> float:
    """
    Intelligent Kitchen Order Prioritization Algorithm:
    Score formula:
    Priority = (Elapsed Waiting Time * 1.8)
             + (Complexity Weight * Prep Time)
             + (Item Count * 0.5)
             + (Delay Factor)
    """
    base_wait_weight = elapsed_minutes * 1.8
    prep_weight = order.estimated_prep_minutes * 0.6
    items_count = len(order.items) if order.items else 1
    items_weight = min(items_count * 0.8, 8.0)
    
    delay_penalty = 0.0
    if elapsed_minutes > 15:
        delay_penalty = (elapsed_minutes - 15) * 3.5

    priority_score = round(base_wait_weight + prep_weight + items_weight + delay_penalty, 2)
    return priority_score

def sort_kitchen_queue(orders: List[Order]) -> List[Dict[str, Any]]:
    """
    Evaluates all active orders in KDS and assigns priority badge & warning flags.
    """
    now = datetime.now(timezone.utc)
    ranked_orders = []

    for order in orders:
        created = order.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = (now - created).total_seconds() / 60.0
        score = calculate_kitchen_priority_score(order, elapsed)
        
        if elapsed > 20 or score > 45:
            urgency = "CRITICAL"
            badge_color = "danger"
        elif elapsed > 10 or score > 25:
            urgency = "HIGH"
            badge_color = "warning"
        else:
            urgency = "NORMAL"
            badge_color = "info"

        ranked_orders.append({
            "order": order,
            "elapsed_minutes": round(elapsed, 1),
            "priority_score": score,
            "urgency": urgency,
            "badge_color": badge_color,
            "is_delayed": elapsed > 20
        })

    # Sort descending by priority score
    ranked_orders.sort(key=lambda x: x["priority_score"], reverse=True)
    return ranked_orders
