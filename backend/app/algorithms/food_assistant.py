import re
import json
import logging
from typing import Dict, Any, List, Optional
import httpx
from sqlmodel import Session, select
from app.models.menu import MenuItem
from app.models.restaurant import Restaurant
from app.models.order import Order
from app.models.enums import OrderStatus
from app.models.user import CustomerPreference
from app.config import settings

logger = logging.getLogger(__name__)


def _allergy_terms(value: Optional[str]) -> List[str]:
    return [term.strip().casefold() for term in re.split(r"[,;/]", value or "") if term.strip() and term.strip().casefold() not in {"none", "no allergies", "n/a"}]


def _contains_term(text: Optional[str], term: str) -> bool:
    return bool(text and re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text.casefold()))


def _dish_is_safe_for_allergies(item: MenuItem, allergies: List[str]) -> bool:
    details = f"{item.allergens or ''} {item.ingredients or ''}"
    for allergy in allergies:
        candidates = [allergy]
        if allergy in {"nut", "nuts", "tree nut", "tree nuts"}:
            candidates.extend(["peanut", "peanuts", "almond", "almonds", "cashew", "cashews", "walnut", "walnuts", "pistachio", "pistachios"])
        elif allergy in {"peanut", "peanuts"}:
            candidates.extend(["nut", "nuts", "tree nut", "tree nuts"])
        elif allergy in {"milk", "dairy"}:
            candidates.extend(["milk", "dairy", "butter", "cream", "cheese", "ghee"])
        if any(_contains_term(details, candidate) for candidate in candidates):
            return False
    return True

def _process_food_chat_local(
    session: Session,
    message: str,
    user_id: Optional[int] = None,
    restaurant_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    AI Conversational Food Assistant:
    Searches the real menu database, checks vegetarian status, price bounds, ingredients,
    allergens, and active orders. Never invents items or prices.
    Returns formatted response with interactive items ready for Add to Cart.
    """
    clean_msg = message.strip()
    lower_msg = clean_msg.casefold()
    preference = None
    if user_id:
        preference = session.exec(
            select(CustomerPreference).where(CustomerPreference.user_id == user_id)
        ).first()
    allergies = _allergy_terms(preference.allergy_info if preference else None)
    if any(word in lower_msg for word in ("allergy", "allergies", "allergic", "without", "free of", "no ")):
        known_allergens = ("peanuts", "peanut", "tree nuts", "nuts", "dairy", "milk", "gluten", "wheat", "soy", "soya", "egg", "eggs", "fish", "shellfish", "sesame")
        allergies.extend(term for term in known_allergens if _contains_term(lower_msg, term) and term not in allergies)

    # 1. Check for Order Status Query
    if any(phrase in lower_msg for phrase in ["order status", "my order", "where is my order", "track order", "track my food"]):
        if not user_id:
            return {
                "reply": "Please log in to your customer account so I can look up your active order status!",
                "suggestions": ["Show vegetarian food", "What is popular today?", "Food under ₹200"],
                "recommended_items": [],
                "intent": "order_status"
            }
        
        # Look up latest order for this customer
        latest_order = session.exec(
            select(Order)
            .where(Order.customer_id == user_id)
            .order_by(Order.created_at.desc())
        ).first()

        if not latest_order:
            return {
                "reply": "You don't have any placed orders yet. Would you like to explore today's popular dishes?",
                "suggestions": ["Show vegetarian food", "What is popular today?", "Food under ₹150"],
                "recommended_items": [],
                "intent": "order_status"
            }
        
        status_map = {
            OrderStatus.PENDING: "🕒 Received and awaiting restaurant confirmation.",
            OrderStatus.CONFIRMED: "✅ Confirmed by restaurant and sent to kitchen.",
            OrderStatus.PREPARING: "🍳 Our chefs are preparing your delicious food right now!",
            OrderStatus.READY: "📦 Ready and waiting for delivery partner pickup.",
            OrderStatus.OUT_FOR_DELIVERY: "🛵 On its way! Your delivery partner is riding to your address.",
            OrderStatus.DELIVERED: "🎉 Delivered! Enjoy your meal.",
            OrderStatus.CANCELLED: "❌ Order was cancelled."
        }
        
        reply = (
            f"📦 **Order #{latest_order.order_number}**\n\n"
            f"**Status**: {status_map.get(latest_order.status, latest_order.status.value)}\n"
            f"**Total Amount**: ₹{latest_order.total_amount:.2f}\n"
            f"**Estimated Delivery**: {latest_order.estimated_delivery_minutes} minutes"
        )
        return {
            "reply": reply,
            "suggestions": ["Track on map", "What is popular today?", "Suggest food under ₹200"],
            "recommended_items": [],
            "intent": "order_status"
        }

    # 2. Check for Ingredient / Allergen Query for specific item
    # e.g., "What ingredients are in Paneer Butter Masala?", "Does Masala Dosa have gluten?"
    ingredient_match = re.search(r"(?:ingredient|recipe|what is in|what's in|what is inside|contain|allerg(?:y|en|ies))\s+(?:the\s+)?([a-zA-Z\s]+)", lower_msg)
    if ingredient_match or "ingredient" in lower_msg:
        # Search menu items matching the text
        all_items = session.exec(select(MenuItem)).all()
        target_item = None
        for item in all_items:
            if item.name.lower() in lower_msg:
                target_item = item
                break
        
        if target_item:
            allergen_text = target_item.allergens if target_item.allergens else "None reported"
            item_safe = _dish_is_safe_for_allergies(target_item, allergies)
            reply = (
                f"🍲 **{target_item.name}**\n\n"
                f"• **Key Ingredients**: {target_item.ingredients or 'Fresh chef recipe'}\n"
                f"• **Allergen Information**: {allergen_text}\n"
                f"• **Dietary Type**: {'🟢 100% Vegetarian' if target_item.is_veg else '🔴 Non-Vegetarian'}\n"
                f"• **Price**: ₹{target_item.price:.2f}"
            )
            if not item_safe:
                reply += "\n\n⚠️ This dish may contain an allergen from your saved profile, so I have not added it as a recommendation. Please confirm ingredients with the restaurant before ordering."
            return {
                "reply": reply,
                "suggestions": [f"Order {target_item.name}", "Suggest vegetarian food under ₹200", "What is popular today?"],
                "recommended_items": ([{
                    "food_id": target_item.id,
                    "name": target_item.name,
                    "price": target_item.discount_price or target_item.price,
                    "image_url": target_item.image_url,
                    "restaurant_name": target_item.restaurant.name if target_item.restaurant else "AI Foodie Kitchen",
                    "is_veg": target_item.is_veg
                }] if item_safe else []),
                "intent": "ingredient_inquiry"
            }

    # 3. Price & Veg Filter Extraction
    # Look for price like "under 200", "< 150", "below ₹200", "under ₹150"
    max_price = None
    price_match = re.search(r"(?:under|below|less than|within|budget(?: of)?|<=?)\s*(?:₹|rs\.?|inr|\$)?\s*(\d+(?:\.\d+)?)", lower_msg)
    if not price_match:
        price_match = re.search(r"(?:₹|rs\.?|inr|\$)\s*(\d+(?:\.\d+)?)", lower_msg)
    if price_match:
        try:
            max_price = float(price_match.group(1))
        except ValueError:
            max_price = None

    # Determine veg filter
    is_veg_query = None
    if re.search(r"\b(non[- ]?veg|chicken|meat|egg|fish|seafood)\b", lower_msg):
        is_veg_query = False
    elif re.search(r"\b(vegetarian|veg|vegan|jain|no meat)\b", lower_msg):
        is_veg_query = True
    elif preference and preference.dietary_preference.casefold() in {"veg", "vegetarian", "vegan", "jain"}:
        is_veg_query = True

    # Check for category / cuisine keywords
    cuisine_keywords = {
        "south indian": ["dosa", "idli", "vada", "south indian", "meals", "sambar"],
        "north indian": ["paneer", "naan", "dal", "curry", "north indian", "roti"],
        "pizza": ["pizza", "margherita", "garlic bread", "cheese burst"],
        "burger": ["burger", "fries", "wrap", "sandwich"],
        "biryani": ["biryani", "rice", "fried rice"],
        "chinese": ["manchurian", "fried rice", "noodles", "chilli"],
        "dessert": ["dessert", "sweet", "brownie", "gulab jamun", "shake", "ice cream"],
        "beverage": ["shake", "drink", "beverage", "tea", "coffee"]
    }

    detected_category = None
    for cat, kws in cuisine_keywords.items():
        if any(kw in lower_msg for kw in kws):
            detected_category = cat
            break

    # 4. Check for Popularity
    is_popular_query = any(w in lower_msg for w in ["popular", "best", "bestseller", "top", "trending", "special", "recommend"])

    # Build DB Query
    query = select(MenuItem).where(MenuItem.is_available == True)

    if restaurant_id:
        query = query.where(MenuItem.restaurant_id == restaurant_id)

    if is_veg_query is not None:
        query = query.where(MenuItem.is_veg == is_veg_query)

    items = session.exec(query).all()
    if allergies:
        items = [item for item in items if _dish_is_safe_for_allergies(item, allergies)]
    dietary_preference = preference.dietary_preference.casefold() if preference else ""
    if dietary_preference in {"vegan", "jain", "gluten-free", "dairy-free"}:
        required_tag = dietary_preference.replace("-", " ")
        items = [item for item in items if required_tag in (item.dietary_tags or "").casefold().replace("-", " ")]

    # Filter by price if requested
    if max_price:
        items = [i for i in items if (i.discount_price or i.price) <= max_price]

    # Filter or boost by category
    if detected_category:
        matched_category_items = [
            i for i in items if (
                (i.category and detected_category in i.category.name.lower()) or
                (detected_category in i.name.lower()) or
                (detected_category in i.description.lower())
            )
        ]
        items = matched_category_items

    # Sort by popularity / rating
    items.sort(key=lambda x: (x.is_bestseller, x.rating, x.total_orders_count), reverse=True)
    selected_items = items[:5]

    if selected_items:
        formatted_items = []
        for i in selected_items:
            formatted_items.append({
                "food_id": i.id,
                "name": i.name,
                "price": i.discount_price or i.price,
                "image_url": i.image_url,
                "restaurant_name": i.restaurant.name if i.restaurant else "AI Foodie",
                "is_veg": i.is_veg
            })

        criteria_parts = []
        if is_veg_query is True:
            criteria_parts.append("vegetarian")
        elif is_veg_query is False:
            criteria_parts.append("non-vegetarian")
        if max_price:
            criteria_parts.append(f"under ₹{int(max_price)}")
        if detected_category:
            criteria_parts.append(f"{detected_category.title()}")

        criteria_str = " ".join(criteria_parts) if criteria_parts else "top recommended"
        
        reply = (
            f"Here are {len(selected_items)} delicious {criteria_str} options available right now in our live menu! "
            f"You can add any dish directly to your cart with one tap:"
        )

        return {
            "reply": reply,
            "suggestions": [
                "Show food under ₹150",
                "What is popular today?",
                "What ingredients are in Paneer Butter Masala?",
                "What is my current order status?"
            ],
            "recommended_items": formatted_items,
            "intent": "food_recommendation"
        }
    else:
        # Fallback when no direct filter match
        return {
            "reply": (
                f"I couldn't find any dishes exactly matching your query "
                f"({f'under ₹{int(max_price)}' if max_price else ''}). "
                f"Try browsing our popular dishes or ask for vegetarian specials under ₹200!"
            ),
            "suggestions": [
                "Suggest vegetarian food under ₹200",
                "What is popular today?",
                "Show food under ₹150"
            ],
            "recommended_items": [],
            "intent": "no_match"
        }


def _generate_llm_reply(message: str, local_result: Dict[str, Any], conversation_history: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    """Rewrite the grounded local answer conversationally; never let the LLM create cart actions."""
    api_key = settings.OPENAI_API_KEY or settings.GEMINI_API_KEY
    if not api_key:
        return None

    # Only send the facts already selected from our own database. User/order data is not sent.
    context = {
        "intent": local_result.get("intent"),
        "grounded_reply": local_result.get("reply"),
        "available_menu_items": local_result.get("recommended_items", []),
    }
    prompt = (
        "Answer the customer's latest message using only the verified application facts below. "
        "Do not invent dishes, ingredients, prices, availability, order details, or promises. "
        "If the facts do not answer the question, say so briefly. Never place an order or claim one was placed. "
        "Return only the customer-facing reply.\n\n"
        f"Customer message: {message}\nVerified application facts: {json.dumps(context, ensure_ascii=False)}"
    )
    messages = [{"role": "system", "content": "You are AI Foodie. Follow the grounding rules in the current user message."}]
    for entry in (conversation_history or [])[-8:]:
        role = entry.get("role")
        content = entry.get("content", "")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()[:1000]})
    messages.append({"role": "user", "content": prompt})
    try:
        with httpx.Client(timeout=12.0) as client:
            if settings.OPENAI_API_KEY:
                response = client.post(
                    settings.OPENAI_API_URL,
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={
                        "model": settings.OPENAI_MODEL,
                        "messages": messages,
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                reply = response.json()["choices"][0]["message"]["content"]
            else:
                response = client.post(
                    settings.GEMINI_API_URL,
                    params={"key": settings.GEMINI_API_KEY},
                    json={"contents": [
                        *[{"role": "model" if entry["role"] == "assistant" else "user", "parts": [{"text": entry["content"]}]} for entry in messages[1:-1]],
                        {"role": "user", "parts": [{"text": messages[0]["content"] + "\n\n" + prompt}]},
                    ], "generationConfig": {"temperature": 0.2}},
                )
                response.raise_for_status()
                reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            reply = reply.strip()
            return reply[:2000] if reply else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        # Do not log provider exception text: Gemini errors can include the API key in the URL.
        logger.warning("Food assistant LLM request failed (%s); using local response", type(exc).__name__)
        return None


def process_food_chat(
    session: Session,
    message: str,
    user_id: Optional[int] = None,
    restaurant_id: Optional[int] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Use the local database-backed assistant, optionally polished by a configured LLM."""
    result = _process_food_chat_local(session, message, user_id, restaurant_id)
    llm_reply = _generate_llm_reply(message, result, conversation_history)
    if llm_reply:
        result["reply"] = llm_reply
        result["llm_used"] = True
    else:
        result["llm_used"] = False
    return result
