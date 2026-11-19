from app.models.restaurant import Restaurant
from app.models.category import Category
from app.models.menu import MenuItem
from app.models.user import User, CustomerPreference
from app.models.enums import UserRole
from app.algorithms.delivery_dispatch import haversine_distance_km, calculate_delivery_eta
from app.services.auth_service import create_access_token

def test_ai_personalized_recommendations(client, session):
    cust = User(email="customer@demo.com", hashed_password="pw", full_name="Customer", role=UserRole.CUSTOMER)
    session.add(cust)
    session.commit()
    session.refresh(cust)
    assert cust.id is not None

    pref = CustomerPreference(user_id=cust.id, dietary_preference="Veg", allergy_info="Nuts")
    session.add(pref)

    rest = Restaurant(name="Spice Garden", description="Desc", address="Indiranagar", image_url="http://img.jpg")
    session.add(rest)
    session.commit()
    session.refresh(rest)
    assert rest.id is not None

    cat = Category(name="South Indian", slug="south-indian")
    session.add(cat)
    session.commit()
    session.refresh(cat)
    assert cat.id is not None

    safe_veg_item = MenuItem(
        restaurant_id=rest.id, category_id=cat.id, name="Masala Dosa",
        description="Crisp dosa", price=80.0, is_veg=True, allergens="None",
        is_available=True, rating=4.9, image_url="http://dosa.jpg"
    )
    allergen_item = MenuItem(
        restaurant_id=rest.id, category_id=cat.id, name="Nut Kheer",
        description="Sweet with nuts", price=120.0, is_veg=True, allergens="Nuts",
        is_available=True, rating=4.8, image_url="http://kheer.jpg"
    )
    session.add(safe_veg_item)
    session.add(allergen_item)
    session.commit()

    token = create_access_token({"sub": cust.email})
    recs_res = client.get(
        f"/api/ai/recommendations?user_id={cust.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recs_res.status_code == 200
    recs = recs_res.json()
    assert len(recs) >= 1
    # Top match should be safe veg item, not the item with nuts
    assert recs[0]["name"] == "Masala Dosa"
    spoofed_recs = client.get(f"/api/ai/recommendations?user_id={cust.id}")
    assert spoofed_recs.status_code == 200
    assert {item["name"] for item in spoofed_recs.json()} == {"Masala Dosa", "Nut Kheer"}

def test_ai_food_assistant_chat(client, session):
    # Setup dish
    rest = Restaurant(name="Spice Garden", description="Desc", address="Indiranagar", image_url="http://img.jpg")
    session.add(rest)
    session.commit()
    session.refresh(rest)
    assert rest.id is not None

    cat = Category(name="South Indian", slug="south-indian")
    session.add(cat)
    session.commit()
    session.refresh(cat)
    assert cat.id is not None

    item = MenuItem(
        restaurant_id=rest.id, category_id=cat.id,
        name="Masala Dosa", description="Crisp dosa", price=80.0,
        ingredients="Fermented rice batter, potato masala, ghee",
        allergens="None", is_veg=True, is_available=True, image_url="http://dosa.jpg"
    )
    session.add(item)
    session.commit()

    # Query 1: "Suggest vegetarian food under ₹200"
    chat_res = client.post("/api/ai/chat", json={"message": "Suggest vegetarian food under ₹200"})
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert len(data["recommended_items"]) > 0
    assert data["recommended_items"][0]["name"] == "Masala Dosa"
    assert data["recommended_items"][0]["price"] == 80.0

    # Query 2: "What ingredients are in Masala Dosa?"
    ing_res = client.post("/api/ai/chat", json={"message": "What ingredients are in Masala Dosa?"})
    assert ing_res.status_code == 200
    assert "Fermented rice batter" in ing_res.json()["reply"]

def test_chat_parses_rupee_budget_and_applies_saved_allergies(client, session):
    rest = Restaurant(name="Safe Kitchen", description="Desc", address="Bengaluru", image_url="https://example.test/r.png")
    user = User(email="safe-customer@test.local", hashed_password="x", full_name="Safe Customer", role=UserRole.CUSTOMER)
    session.add_all([rest, user]); session.commit(); session.refresh(rest); session.refresh(user)
    assert rest.id is not None and user.id is not None
    category = Category(name="Meals", slug="safe-meals"); session.add(category); session.commit(); session.refresh(category)
    assert category.id is not None
    session.add(CustomerPreference(user_id=user.id, dietary_preference="Veg", allergy_info="peanuts"))
    session.add_all([
        MenuItem(restaurant_id=rest.id, category_id=category.id, name="Safe Dosa", description="Plain", image_url="https://example.test/d.png", price=90, is_veg=True, ingredients="rice batter", allergens="None"),
        MenuItem(restaurant_id=rest.id, category_id=category.id, name="Peanut Dosa", description="Peanut chutney", image_url="https://example.test/p.png", price=80, is_veg=True, ingredients="rice batter, peanuts", allergens="Peanuts"),
        MenuItem(restaurant_id=rest.id, category_id=category.id, name="Chicken Meal", description="Chicken", image_url="https://example.test/c.png", price=100, is_veg=False, ingredients="chicken", allergens="None"),
        MenuItem(restaurant_id=rest.id, category_id=category.id, name="Expensive Dosa", description="Plain", image_url="https://example.test/e.png", price=250, is_veg=True, ingredients="rice batter", allergens="None"),
    ]); session.commit()

    token = create_access_token({"sub": user.email})
    response = client.post("/api/ai/chat", json={"message": "Suggest vegetarian food under ₹200"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert {item["name"] for item in data["recommended_items"]} == {"Safe Dosa"}

def test_chat_does_not_disclose_another_users_order_by_request_user_id(client, session):
    customer = User(email="private-customer@test.local", hashed_password="x", full_name="Private Customer", role=UserRole.CUSTOMER)
    restaurant = Restaurant(name="Private Kitchen", description="Desc", address="Bengaluru", image_url="https://example.test/r.png")
    session.add_all([customer, restaurant]); session.commit(); session.refresh(customer); session.refresh(restaurant)
    assert customer.id is not None and restaurant.id is not None
    from app.models.order import Order
    from app.models.enums import OrderStatus
    session.add(Order(order_number="PRIVATE-ORDER", customer_id=customer.id, restaurant_id=restaurant.id, status=OrderStatus.PREPARING, delivery_address="Secret address"))
    session.commit()
    response = client.post("/api/ai/chat", json={"message": "What is my order status?", "user_id": customer.id})
    assert response.status_code == 200
    assert "log in" in response.json()["reply"].lower()
    assert "PRIVATE-ORDER" not in response.json()["reply"]

def test_chat_rejects_blank_message(client):
    response = client.post("/api/ai/chat", json={"message": "   "})
    assert response.status_code == 422

def test_delivery_dispatch_and_eta():
    # Test distance between Indiranagar and Koramangala (~5 km)
    dist = haversine_distance_km(12.9784, 77.6408, 12.9352, 77.6245)
    assert 4.0 <= dist <= 6.5

    # Test ETA formula: 15 min prep + distance * 4.5
    eta = calculate_delivery_eta(dist, 15)
    assert 30 <= eta <= 50

def test_demand_prediction_empty_and_populated(client, session, admin_headers):
    admin = User(email="admin@demo.com", hashed_password="pw", full_name="Admin", role=UserRole.RESTAURANT_ADMIN)
    session.add(admin)
    session.commit()
    session.refresh(admin)
    headers = admin_headers

    # 1. Empty database returns empty list
    assert client.get("/api/ai/demand-forecast").status_code == 401
    assert client.get("/api/ai/smart-inventory").status_code == 401
    res = client.get("/api/ai/demand-forecast", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    # 2. Add restaurant, category, and menu item
    rest = Restaurant(name="Spice Garden", description="Desc", address="Indiranagar", image_url="http://img.jpg", owner_id=admin.id)
    session.add(rest)
    session.commit()
    session.refresh(rest)

    cat = Category(name="South Indian", slug="south-indian")
    session.add(cat)
    session.commit()
    session.refresh(cat)

    item = MenuItem(
        restaurant_id=rest.id, category_id=cat.id,
        name="Masala Dosa", description="Crisp dosa", price=80.0,
        is_veg=True, allergens="None", is_available=True, rating=4.9, image_url="http://dosa.jpg",
        total_orders_count=10, is_bestseller=True
    )
    session.add(item)
    session.commit()

    # Query without orders (fallback logic)
    forecast_res = client.get(f"/api/ai/demand-forecast?restaurant_id={rest.id}", headers=headers)
    assert forecast_res.status_code == 200
    forecast_data = forecast_res.json()
    assert len(forecast_data) == 1
    dosa_forecast = forecast_data[0]
    assert dosa_forecast["item_name"] == "Masala Dosa"
    assert dosa_forecast["predicted_demand_next_day"] >= 8
    assert dosa_forecast["recommended_prep_qty"] >= dosa_forecast["predicted_demand_next_day"]
    assert dosa_forecast["stock_status"] == "Sufficient"
    assert dosa_forecast["current_price"] == 80.0

