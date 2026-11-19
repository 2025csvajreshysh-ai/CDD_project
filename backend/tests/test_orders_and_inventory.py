from app.models.restaurant import Restaurant
from app.models.category import Category
from app.models.menu import MenuItem, RecipeItem
from app.models.inventory import Ingredient
from app.models.user import User
from app.models.delivery import DeliveryProfile
from app.models.order import Order
from app.models.enums import UserRole, OrderStatus
from app.algorithms.kitchen_priority import calculate_kitchen_priority_score

def test_order_placement_inventory_deduction_and_priority(client, session, auth_headers, kitchen_headers, delivery_headers):
    # Setup database
    cust = User(email="customer@demo.com", hashed_password="pw", full_name="Customer", role=UserRole.CUSTOMER)
    session.add(cust)
    driver = User(email="delivery@demo.com", hashed_password="pw", full_name="Driver", role=UserRole.DELIVERY_PARTNER)
    session.add(driver)
    kitchen_staff = User(email="kitchen@demo.com", hashed_password="pw", full_name="Kitchen", role=UserRole.KITCHEN_STAFF)
    session.add(kitchen_staff)

    rest = Restaurant(name="Spice Garden", description="Desc", address="Indiranagar", image_url="http://img.jpg")
    session.add(rest)
    session.commit()
    session.refresh(rest)
    assert rest.id is not None
    session.refresh(driver)
    session.add(DeliveryProfile(user_id=driver.id, current_latitude=12.9716, current_longitude=77.5946, is_available=True))
    session.commit()

    cat = Category(name="South Indian", slug="south-indian")
    session.add(cat)
    session.commit()
    session.refresh(cat)
    assert cat.id is not None

    menu_item = MenuItem(
        restaurant_id=rest.id, category_id=cat.id,
        name="Masala Dosa", description="Dosa", price=80.0,
        prep_time_minutes=15, is_veg=True, image_url="http://dosa.jpg"
    )
    session.add(menu_item)
    session.commit()
    session.refresh(menu_item)
    assert menu_item.id is not None

    # Ingredient with low stock threshold
    ingredient = Ingredient(
        restaurant_id=rest.id, name="Dosa Batter",
        current_stock=10.0, reorder_level=5.0, cost_per_unit=40.0
    )
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    assert ingredient.id is not None

    recipe = RecipeItem(
        menu_item_id=menu_item.id,
        ingredient_id=ingredient.id,
        quantity_required=1.0  # 1kg per serving
    )
    session.add(recipe)
    session.commit()

    # Place an order for 6 Dosas -> Should deduct 6kg -> remaining 4kg <= reorder_level (5.0) -> triggers low stock!
    order_payload = {
        "restaurant_id": rest.id,
        "items": [{"menu_item_id": menu_item.id, "quantity": 6}],
        "delivery_address": "Koramangala, Bangalore",
        "payment_method": "cod"
    }

    order_res = client.post("/api/orders", json=order_payload, headers=auth_headers)
    assert order_res.status_code == 201
    order_data = order_res.json()
    assert order_data["success"] is True
    assert "order_id" in order_data
    assert len(order_data["inventory_alerts"]) > 0
    assert order_data["inventory_alerts"][0]["status"] == "LOW_STOCK"

    # Verify updated ingredient stock in database
    session.refresh(ingredient)
    assert ingredient.current_stock == 4.0
    assert ingredient.is_low_stock is True

    # Test Kitchen Queue
    assert client.get("/api/kitchen/queue").status_code == 401
    assert client.get("/api/kitchen/queue", headers=auth_headers).status_code == 403
    k_res = client.get("/api/kitchen/queue", headers=kitchen_headers)
    assert k_res.status_code == 200
    queue = k_res.json()
    assert len(queue) >= 1
    assert queue[0]["order_id"] == order_data["order_id"]
    assert "priority_score" in queue[0]

    # Test Kitchen Action: Accept -> Preparing -> Ready
    action_url = f"/api/kitchen/orders/{order_data['order_id']}/action"
    assert client.post(f"{action_url}?action=accept").status_code == 401
    action_res = client.post(f"{action_url}?action=accept", headers=kitchen_headers)
    assert action_res.status_code == 200
    assert action_res.json()["new_status"] == "confirmed"
    order = session.get(Order, order_data["order_id"])
    assert order is not None and order.delivery_partner_id == driver.id
    premature_pickup = client.post(
        f"/api/delivery/orders/{order_data['order_id']}/action?action=picked_up",
        headers=delivery_headers,
    )
    assert premature_pickup.status_code == 409
    premature_delivery = client.post(
        f"/api/delivery/orders/{order_data['order_id']}/action?action=delivered",
        headers=delivery_headers,
    )
    assert premature_delivery.status_code == 409

    prepare_res = client.post(f"{action_url}?action=prepare", headers=kitchen_headers)
    assert prepare_res.status_code == 200
    ready_res = client.post(f"{action_url}?action=ready", headers=kitchen_headers)
    assert ready_res.status_code == 200
    handover_res = client.post(f"{action_url}?action=complete", headers=kitchen_headers)
    assert handover_res.status_code == 200
    assert handover_res.json()["new_status"] == OrderStatus.OUT_FOR_DELIVERY.value

    delivered_res = client.post(
        f"/api/delivery/orders/{order_data['order_id']}/action?action=delivered",
        headers=delivery_headers,
    )
    assert delivered_res.status_code == 200
    repeated_delivery = client.post(
        f"/api/delivery/orders/{order_data['order_id']}/action?action=delivered",
        headers=delivery_headers,
    )
    assert repeated_delivery.status_code == 409
    completed_queue = client.get("/api/kitchen/queue?include_completed=true", headers=kitchen_headers)
    assert completed_queue.status_code == 200
    assert any(item["status"] == "delivered" for item in completed_queue.json())

    invalid_repeat = client.post(f"{action_url}?action=accept", headers=kitchen_headers)
    assert invalid_repeat.status_code == 409


def test_restaurant_admin_kitchen_access_is_limited_to_owned_restaurants(client, session, admin_headers):
    admin = User(email="admin@demo.com", hashed_password="pw", full_name="Admin", role=UserRole.RESTAURANT_ADMIN)
    other_owner = User(email="other-admin@test.com", hashed_password="pw", full_name="Other Admin", role=UserRole.RESTAURANT_ADMIN)
    customer = User(email="customer@test.com", hashed_password="pw", full_name="Customer", role=UserRole.CUSTOMER)
    session.add_all([admin, other_owner, customer])
    session.commit()
    session.refresh(admin)
    session.refresh(other_owner)
    session.refresh(customer)

    other_restaurant = Restaurant(
        name="Other Restaurant", description="Desc", address="Bengaluru",
        image_url="https://example.test/restaurant.png", owner_id=other_owner.id,
    )
    session.add(other_restaurant)
    session.commit()
    session.refresh(other_restaurant)

    foreign_order = Order(
        order_number="ORD-FOREIGN", customer_id=customer.id, restaurant_id=other_restaurant.id,
        delivery_address="Bengaluru",
    )
    session.add(foreign_order)
    session.commit()
    session.refresh(foreign_order)

    queue_response = client.get(
        f"/api/kitchen/queue?restaurant_id={other_restaurant.id}", headers=admin_headers
    )
    action_response = client.post(
        f"/api/kitchen/orders/{foreign_order.id}/action?action=accept", headers=admin_headers
    )
    assert queue_response.status_code == 403
    assert action_response.status_code == 403

    unscoped_stats = client.get("/api/admin/dashboard-stats", headers=admin_headers)
    foreign_stats = client.get(
        f"/api/admin/dashboard-stats?restaurant_id={other_restaurant.id}", headers=admin_headers
    )
    foreign_status = client.patch(
        f"/api/orders/{foreign_order.id}/status",
        json={"status": "confirmed"},
        headers=admin_headers,
    )
    assert unscoped_stats.status_code == 200
    assert unscoped_stats.json()["total_orders"] == 0
    assert foreign_stats.status_code == 403
    assert foreign_status.status_code == 403
