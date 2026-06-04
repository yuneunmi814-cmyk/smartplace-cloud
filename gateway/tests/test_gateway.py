import os

os.environ["GATEWAY_KEY"] = "test-key"
os.environ["GATEWAY_MOCK"] = "1"

import json  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-key"}


def test_health_reports_mock():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mock"] is True


def test_apply_requires_gateway_key():
    r = client.post("/places/123/main-image", json={"imageUrl": "http://x/y.png"})
    assert r.status_code == 401


def test_apply_succeeds_in_mock_mode():
    cred = json.dumps({"loginId": "demo", "loginPw": "secret"})
    r = client.post(
        "/places/123/main-image",
        headers={**AUTH, "X-Naver-Account-Token": cred},
        json={"imageUrl": "https://s3.example.com/img.png"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
