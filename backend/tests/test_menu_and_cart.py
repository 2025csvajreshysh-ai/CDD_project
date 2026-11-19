from app.models.restaurant import Restaurant
from app.models.category import Category
from app.models.menu import MenuItem
from app.models.user import User
from app.models.enums import UserRole

def test_menu_filtering_and_cart_flow(client, session, auth_headers):
    # Seed user, restaurant, category, and items
    cust = User(email="customer@demo.com", hashed_password="pw", full_name="Customer", role=UserRole.CUSTOMER)
    session.add(cust)
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

    item1 = MenuItem(
        restaurant_id=rest.id, category_id=cat.id,
        name="Masala Dosa", description="Crisp crepe", price=80.0,
        is_veg=True, allergens="None", image_url="http://dosa.jpg"
    )
    item2 = MenuItem(
        restaurant_id=rest.id, category_id=cat.id,
        name="Butter Chicken", description="Creamy chicken", price=250.0,
        is_veg=False, allergens="Dairy, Nuts", image_url="http://chicken.jpg"
    )
    session.add(item1)
    session.add(item2)
    session.commit()
    session.refresh(item1)
    session.refresh(item2)
    assert item1.id is not None and item2.id is not None

    # 1. Test Menu Listing & Veg Filter
    res_all = client.get("/api/menu")
    assert res_all.status_code == 200
    assert len(res_all.json()) == 2

    res_veg = client.get("/api/menu?is_veg=true")
    assert len(res_veg.json()) == 1
    assert res_veg.json()[0]["name"] == "Masala Dosa"

    # 2. Test Allergen Filter
    res_nut_free = client.get("/api/menu?allergen_free=nuts")
    assert len(res_nut_free.json()) == 1
    assert res_nut_free.json()[0]["name"] == "Masala Dosa"

    # 3. Test Cart Flow
    # Add to cart
    add_res = client.post("/api/cart/add", json={"menu_item_id": item1.id, "quantity": 2}, headers=auth_headers)
    assert add_res.status_code == 200

    # Get cart
    cart_res = client.get("/api/cart", headers=auth_headers)
    assert cart_res.status_code == 200
    cart_data = cart_res.json()
    assert cart_data["item_count"] == 2
    assert cart_data["subtotal"] == 160.0

    # Test Coupon Application
    coupon_res = client.post("/api/cart/validate-coupon", json={"code": "AIFOODIE20", "subtotal": 200.0})
    assert coupon_res.status_code == 200
    assert coupon_res.json()["discount_amount"] == 40.0

def test_cross_restaurant_cart_replacement(client, session, auth_headers):
    cust = User(email="customer@demo.com", hashed_password="pw", full_name="Customer", role=UserRole.CUSTOMER)
    session.add(cust)

    # Setup two restaurants with items
    rest1 = Restaurant(name="Spice Garden", description="Dosa Place", address="Indiranagar", image_url="http://img1.jpg")
    rest2 = Restaurant(name="Pizza Palace", description="Pizza Place", address="Koramangala", image_url="http://img2.jpg")
    session.add_all([rest1, rest2])
    session.commit()
    session.refresh(rest1)
    session.refresh(rest2)

    cat = Category(name="Fast Food", slug="fast-food")
    session.add(cat)
    session.commit()
    session.refresh(cat)

    dosa = MenuItem(restaurant_id=rest1.id, category_id=cat.id, name="Masala Dosa", description="Dosa", price=80.0, image_url="http://dosa.jpg")
    brownie = MenuItem(restaurant_id=rest2.id, category_id=cat.id, name="Chocolate Brownie", description="Brownie", price=99.0, image_url="http://brownie.jpg")
    session.add_all([dosa, brownie])
    session.commit()
    session.refresh(dosa)
    session.refresh(brownie)

    # 1. Add Dosa to cart
    res1 = client.post("/api/cart/add", json={"menu_item_id": dosa.id, "quantity": 1}, headers=auth_headers)
    assert res1.status_code == 200

    # 2. Adding Brownie without replace_cart should fail with 400 and clear message
    res2 = client.post("/api/cart/add", json={"menu_item_id": brownie.id, "quantity": 1}, headers=auth_headers)
    assert res2.status_code == 400
    assert "Spice Garden" in res2.json()["detail"]
    assert "Pizza Palace" in res2.json()["detail"]

    # 3. Adding Brownie with replace_cart=True should succeed and replace the cart
    res3 = client.post("/api/cart/add", json={"menu_item_id": brownie.id, "quantity": 1, "replace_cart": True}, headers=auth_headers)
    assert res3.status_code == 200

    # 4. Verify cart now contains only Brownie
    cart = client.get("/api/cart", headers=auth_headers).json()
    assert cart["item_count"] == 1
    assert cart["items"][0]["menu_item_id"] == brownie.id
    assert cart["restaurant_id"] == rest2.id

