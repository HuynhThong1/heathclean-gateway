"""The shared API key that makes the gateway safe to expose.

`GATEWAY_API_KEY` is read per request, so `monkeypatch.setenv` is enough to
exercise both halves — no reimporting the app the way provider configuration
would need.
"""

import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

KEY = "s3cret"


def _image():
    return {"image": ("meal.jpg", io.BytesIO(b"plate-0000"), "image/jpeg")}


def test_without_a_configured_key_the_gateway_stays_open():
    # The local-development default, and what the rest of the suite assumes.
    assert client.post("/v1/meals/analyze", files=_image()).status_code == 200


def test_a_configured_key_is_required(monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    assert client.post("/v1/meals/analyze", files=_image()).status_code == 401


def test_a_wrong_key_is_rejected(monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    response = client.post(
        "/v1/meals/analyze", files=_image(), headers={"X-API-Key": "not-it"}
    )
    assert response.status_code == 401


def test_the_right_key_gets_through(monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    response = client.post(
        "/v1/meals/analyze", files=_image(), headers={"X-API-Key": KEY}
    )
    assert response.status_code == 200


def test_every_v1_route_is_guarded_not_only_analyze(monkeypatch):
    # The informational routes report which keys are configured, so leaving
    # them open would describe the deployment to anyone who asked.
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    assert client.get("/v1/providers").status_code == 401
    assert client.get("/v1/nutrition/sources").status_code == 401


def test_healthz_stays_open(monkeypatch):
    # The container healthcheck has no key, and this endpoint reveals nothing.
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    assert client.get("/healthz").status_code == 200
