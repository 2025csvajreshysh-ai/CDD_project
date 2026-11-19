from typing import List, Optional
from sqlmodel import Session, select, col
from app.models.menu import MenuItem
from app.models.order import Order, OrderItem
from app.models.review import Review
from app.models.user import CustomerPreference
import re


def _normal_terms(value: Optional[str]) -> List[str]:
    return [term.strip().casefold() for term in (value or "").replace(";", ",").split(",") if term.strip() and term.strip().casefold() not in {"none", "n/a", "no allergies"}]


def _allergen_match(item: MenuItem, allergy: str) -> bool:
    terms = [allergy]
    if allergy in {"nut", "nuts", "tree nut", "tree nuts"}:
        terms.extend(["peanut", "peanuts", "almond", "almonds", "cashew", "cashews", "walnut", "walnuts", "pistachio", "pistachios"])
    elif allergy in {"peanut", "peanuts"}:
        terms.extend(["nut", "nuts", "tree nut", "tree nuts"])
    elif allergy in {"milk", "dairy"}:
        terms.extend(["milk", "dairy", "butter", "cream", "cheese", "ghee"])
    details = f"{item.allergens or ''} {item.ingredients or ''}".casefold()
    return any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", details) for term in terms)

def get_personalized_recommendations(
    session: Session,
    user_id: Optional[int] = None,
    restaurant_id: Optional[int] = None,
    limit: int = 6
) -> List[MenuItem]:
    """
    AI Personalized Food Recommendation Engine:
    Combines:
    1. Customer dietary preferences (e.g. Veg / Non-Veg / Vegan / Allergens)
    2. Past ordering history & frequent items
    3. Highly rated dishes and popularity weights
    """
    # Base query for available items
    query = select(MenuItem).where(MenuItem.is_available == True)
    
    if restaurant_id:
        query = query.where(MenuItem.restaurant_id == restaurant_id)
        
    all_items = session.exec(query).all()
    if not all_items:
        return []

    # If no user logged in, return top rated bestsellers
    if not user_id:
        sorted_items = sorted(
            all_items,
            key=lambda x: (x.is_bestseller, x.rating, x.total_orders_count),
            reverse=True
        )
        return sorted_items[:limit]

    # Fetch user preferences
    pref = session.exec(
        select(CustomerPreference).where(CustomerPreference.user_id == user_id)
    ).first()

    if pref:
        dietary = pref.dietary_preference.strip().casefold()
        if dietary in {"veg", "vegetarian", "vegan", "jain"}:
            all_items = [item for item in all_items if item.is_veg]
        if dietary in {"vegan", "jain", "gluten-free", "dairy-free"}:
            required_tag = dietary.replace("-", " ")
            all_items = [item for item in all_items if required_tag in (item.dietary_tags or "").casefold().replace("-", " ")]
        allergies = _normal_terms(pref.allergy_info)
        if allergies:
            all_items = [item for item in all_items if not any(_allergen_match(item, allergy) for allergy in allergies)]

    if not all_items:
        return []

    # Fetch past ordered item IDs
    past_order_ids = session.exec(
        select(Order.id).where(Order.customer_id == user_id)
    ).all()
    
    ordered_item_counts = {}
    if past_order_ids:
        order_items = session.exec(
            select(OrderItem).where(col(OrderItem.order_id).in_(past_order_ids))
        ).all()
        for oi in order_items:
            ordered_item_counts[oi.menu_item_id] = ordered_item_counts.get(oi.menu_item_id, 0) + oi.quantity

    # Fetch user ratings
    user_reviews = session.exec(
        select(Review).where(Review.customer_id == user_id)
    ).all()
    reviewed_item_ratings = {r.menu_item_id: r.rating for r in user_reviews if r.menu_item_id}

    # Score each candidate item
    scored_items = []
    for item in all_items:
        score = 0.0
        
        # 1. Dietary preference compliance
        if pref:
            if pref.dietary_preference.casefold() in {"veg", "vegetarian", "vegan", "jain"} and not item.is_veg:
                score -= 100.0  # Strongly penalize non-veg for veg users
            elif pref.dietary_preference.casefold() in {"veg", "vegetarian", "vegan", "jain"} and item.is_veg:
                score += 15.0
            
        # 2. Past purchase affinity
        past_qty = ordered_item_counts.get(item.id, 0)
        score += min(past_qty * 5.0, 25.0)

        # 3. User past ratings
        if item.id in reviewed_item_ratings:
            score += reviewed_item_ratings[item.id] * 3.0

        # 4. Overall popularity & rating
        score += item.rating * 4.0
        if item.is_bestseller:
            score += 10.0
        if item.is_recommended:
            score += 8.0

        scored_items.append((score, item))

    # Sort descending by calculated score
    scored_items.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored_items[:limit]]
