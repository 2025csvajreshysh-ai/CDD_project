import os
import sys
from pathlib import Path
import pytest
from starlette.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.database import get_session
from app.services.auth_service import create_access_token
from app.models.enums import UserRole

# Use testing in-memory SQLite engine
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    SQLModel.metadata.drop_all(test_engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(name="auth_headers")
def auth_headers_fixture():
    token = create_access_token({"sub": "customer@demo.com", "role": UserRole.CUSTOMER.value, "uid": 1})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(name="admin_headers")
def admin_headers_fixture():
    token = create_access_token({"sub": "admin@demo.com", "role": UserRole.RESTAURANT_ADMIN.value, "uid": 2})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(name="kitchen_headers")
def kitchen_headers_fixture():
    token = create_access_token({"sub": "kitchen@demo.com", "role": UserRole.KITCHEN_STAFF.value, "uid": 3})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(name="delivery_headers")
def delivery_headers_fixture():
    token = create_access_token({"sub": "delivery@demo.com", "role": UserRole.DELIVERY_PARTNER.value, "uid": 4})
    return {"Authorization": f"Bearer {token}"}
