from app.models.delivery import DeliveryProfile
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import create_access_token
from sqlmodel import select


def superadmin_headers(email="platform-admin@test.local"):
    token = create_access_token({"sub": email, "role": UserRole.SUPER_ADMIN.value})
    return {"Authorization": f"Bearer {token}"}


def test_superadmin_creates_delivery_account_and_offline_profile(client, session):
    admin = User(
        email="platform-admin@test.local",
        hashed_password="not-used-by-this-test",
        full_name="Platform Admin",
        role=UserRole.SUPER_ADMIN,
    )
    session.add(admin)
    session.commit()

    response = client.post(
        "/api/superadmin/delivery-partners",
        headers=superadmin_headers(),
        json={
            "full_name": "Rider Example",
            "email": "  RIDER@example.test ",
            "password": "secure-pass-123",
            "phone": "  ",
            "vehicle_type": "Motorcycle",
            "vehicle_number": "KA 01 AB 1234",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["email"] == "rider@example.test"
    assert created["role"] == UserRole.DELIVERY_PARTNER.value
    assert created["is_available"] is False

    partner = session.exec(select(User).where(User.email == "rider@example.test")).one()
    profile = session.exec(select(DeliveryProfile).where(DeliveryProfile.user_id == partner.id)).one()
    assert partner.full_name == "Rider Example"
    assert partner.phone is None
    assert profile.vehicle_type == "Motorcycle"
    assert profile.vehicle_number == "KA 01 AB 1234"
    assert profile.is_available is False

    login = client.post(
        "/api/auth/login",
        json={"email": "rider@example.test", "password": "secure-pass-123"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == UserRole.DELIVERY_PARTNER.value

    partner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    stats = client.get("/api/delivery/stats", headers=partner_headers)
    assert stats.status_code == 200
    assert stats.json()["is_available"] is False
    assert stats.json()["vehicle_number"] == "KA 01 AB 1234"

    availability = client.patch(
        "/api/delivery/availability?is_available=true",
        headers=partner_headers,
    )
    assert availability.status_code == 200
    assert availability.json()["is_available"] is True


def test_delivery_partner_creation_is_superadmin_only(client, session):
    customer = User(
        email="customer@test.local",
        hashed_password="not-used-by-this-test",
        full_name="Customer User",
        role=UserRole.CUSTOMER,
    )
    session.add(customer)
    session.commit()
    customer_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': customer.email})}"
    }

    response = client.post(
        "/api/superadmin/delivery-partners",
        headers=customer_headers,
        json={
            "full_name": "Rider Example",
            "email": "rider@example.test",
            "password": "secure-pass-123",
        },
    )

    assert response.status_code == 403


def test_delivery_partner_creation_rejects_duplicate_email(client, session):
    admin = User(
        email="platform-admin@test.local",
        hashed_password="not-used-by-this-test",
        full_name="Platform Admin",
        role=UserRole.SUPER_ADMIN,
    )
    existing = User(
        email="rider@example.test",
        hashed_password="not-used-by-this-test",
        full_name="Existing Rider",
        role=UserRole.DELIVERY_PARTNER,
    )
    session.add_all([admin, existing])
    session.commit()

    response = client.post(
        "/api/superadmin/delivery-partners",
        headers=superadmin_headers(),
        json={
            "full_name": "Rider Example",
            "email": "RIDER@example.test",
            "password": "secure-pass-123",
        },
    )

    assert response.status_code == 409
