"""Shared fixtures. Isolated SQLite DB + in-memory fakes for S3/Redis/Naver so
the whole stack is testable without external services."""

import os

os.environ["SMARTPLACE_DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SMARTPLACE_TASK_RETRY_BACKOFF_SECONDS"] = "0"
os.environ["SMARTPLACE_TASK_MAX_RETRIES"] = "2"
# Tests assume queue mode (deterministic); ignore any dev .env inline setting.
os.environ["SMARTPLACE_INLINE_DISPATCH"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.naver_gateway import FakeNaverGateway, set_gateway  # noqa: E402
from app.services.queue import InMemoryQueue, set_queue  # noqa: E402
from app.services.storage import InMemoryStorage, set_storage  # noqa: E402


class Fakes:
    def __init__(self):
        self.storage = InMemoryStorage()
        self.queue = InMemoryQueue()
        self.gateway = FakeNaverGateway()


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def fakes():
    f = Fakes()
    set_storage(f.storage)
    set_queue(f.queue)
    set_gateway(f.gateway)
    yield f
    set_storage(None)
    set_queue(None)
    set_gateway(None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth():
    return lambda token: {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_token(client):
    # The first signup is bootstrapped as an approved admin.
    client.post("/api/v1/auth/signup", json={"email": "admin@example.com", "password": "password123"})
    return client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "password123"}
    ).json()["accessToken"]


@pytest.fixture
def user_token(client, admin_token, auth):
    # Second signup is pending → admin approves → returns a usable token.
    client.post("/api/v1/auth/signup", json={"email": "user@example.com", "password": "password123"})
    users = client.get("/api/v1/admin/users", headers=auth(admin_token)).json()
    uid = next(u["id"] for u in users if u["email"] == "user@example.com")
    client.post(f"/api/v1/admin/users/{uid}/approve", headers=auth(admin_token))
    return client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"}
    ).json()["accessToken"]
