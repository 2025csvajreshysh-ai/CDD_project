import pytest
from starlette.websockets import WebSocketDisconnect
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import get_password_hash

def test_register_and_login(client, session):
    # Test Registration
    reg_payload = {
        "email": "newuser@test.com",
        "password": "Password@123",
        "full_name": "Test User",
        "phone": "+91 99999 88888",
        "role": "customer"
    }
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["email"] == "newuser@test.com"

    # Test Duplicate Registration Prevention
    dup_res = client.post("/api/auth/register", json=reg_payload)
    assert dup_res.status_code == 400

    # Test Login
    login_res = client.post("/api/auth/login", json={
        "email": "newuser@test.com",
        "password": "Password@123"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Test Invalid Login
    bad_login = client.post("/api/auth/login", json={
        "email": "newuser@test.com",
        "password": "WrongPassword"
    })
    assert bad_login.status_code == 401

def test_demo_login_all_roles(client, session):
    # Seed demo users
    hashed = get_password_hash("Demo@12345")
    roles = [
        ("customer@demo.com", UserRole.CUSTOMER),
        ("admin@demo.com", UserRole.RESTAURANT_ADMIN),
        ("kitchen@demo.com", UserRole.KITCHEN_STAFF),
        ("delivery@demo.com", UserRole.DELIVERY_PARTNER),
        ("superadmin@demo.com", UserRole.SUPER_ADMIN),
    ]
    for email, role in roles:
        u = User(email=email, hashed_password=hashed, full_name=f"Demo {role.value}", role=role)
        session.add(u)
    session.commit()

    # Verify demo login for each role
    for _, role in roles:
        res = client.post("/api/auth/demo-login", json={"role": role.value})
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == role.value
        assert "access_token" in data


def test_order_websocket_rejects_missing_or_invalid_token(client):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/ws/orders?token=invalid"):
            pass
    assert error.value.code == 4401
