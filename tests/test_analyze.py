import asyncio
import io

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.nutrition.resolver import resolve, total
from app.providers.base import ProviderError, RecognizedFood
from app.providers.gemini import GeminiProvider
from app.providers.prompt import parse_recognition_json
from app.providers.qwen import QwenProvider

client = TestClient(app)


def _image(payload: bytes = b"plate-0000", mime: str = "image/jpeg"):
    return {"image": ("meal.jpg", io.BytesIO(payload), mime)}


def test_health():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_providers_lists_every_model_and_whether_it_is_usable():
    body = client.get("/v1/providers").json()
    names = {entry["name"] for entry in body["providers"]}
    assert names == {"mock", "gemini", "qwen"}
    # Mock needs no configuration; the hosted ones need keys that are not set.
    configured = {entry["name"]: entry["configured"] for entry in body["providers"]}
    assert configured["mock"] is True


def test_nutrition_sources_report_configuration_and_lookup_order():
    assert client.get("/v1/nutrition/sources").json() == {
        "sources": [{"name": "local", "configured": True}]
    }


def test_analyze_returns_items_and_a_total():
    response = client.post("/v1/meals/analyze", files=_image())
    assert response.status_code == 200
    body = response.json()

    assert body["provider"] == "mock"
    assert body["items"], "mock provider should recognise something"
    for item in body["items"]:
        assert item["weight"] > 0
        assert 0.0 <= item["confidence"] <= 1.0
        if item["resolved"]:
            assert item["nutritionSource"] == "local_reference"
            assert item["nutritionIsReference"] is True

    # The total is the sum of the items, not a separate claim.
    assert body["total"]["calories"] == pytest.approx(
        round(sum(item["calories"] for item in body["items"]), 0)
    )


def test_the_same_photo_always_gives_the_same_plate():
    first = client.post("/v1/meals/analyze", files=_image()).json()
    second = client.post("/v1/meals/analyze", files=_image()).json()
    assert first["items"] == second["items"]


def test_provider_can_be_chosen_per_request():
    response = client.post(
        "/v1/meals/analyze",
        files=_image(),
        headers={"X-Model-Provider": "mock"},
    )
    assert response.json()["provider"] == "mock"


def test_an_unknown_provider_is_rejected_rather_than_silently_substituted():
    response = client.post(
        "/v1/meals/analyze",
        files=_image(),
        headers={"X-Model-Provider": "does-not-exist"},
    )
    assert response.status_code == 400
    assert "Unknown model provider" in response.json()["detail"]


def test_a_provider_without_a_key_fails_as_a_gateway_error():
    # gemini has no API key in this environment; that is a 502, not a 400 —
    # the request was fine, the model behind it was not.
    response = client.post(
        "/v1/meals/analyze", files=_image(), headers={"X-Model-Provider": "gemini"}
    )
    assert response.status_code == 502


@pytest.mark.parametrize(
    "provider_factory, environment",
    [
        (GeminiProvider, {"GEMINI_API_KEY": "test-key"}),
        (QwenProvider, {"QWEN_BASE_URL": "https://qwen.invalid/v1"}),
    ],
)
def test_provider_transport_failures_are_retryable_gateway_errors(
    monkeypatch, provider_factory, environment
):
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    async def fail_request(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_request)
    provider = provider_factory()

    with pytest.raises(ProviderError, match="request failed"):
        asyncio.run(provider.recognize(b"image", "image/jpeg"))


def test_non_images_and_empty_uploads_are_rejected():
    assert client.post("/v1/meals/analyze", files=_image(mime="text/plain")).status_code == 415
    assert client.post("/v1/meals/analyze", files=_image(payload=b"")).status_code == 400


# MARK: resolver


def test_nutrition_scales_with_grams():
    items = resolve([RecognizedFood("Cơm trắng", 200.0, 0.9)])
    # 130 kcal / 100 g at 200 g
    assert items[0].calories == 260
    assert items[0].resolved is True
    assert items[0].nutrition_source == "local_reference"
    assert items[0].nutrition_is_reference is True


def test_an_unknown_food_keeps_its_weight_and_reports_zero_nutrition():
    items = resolve([RecognizedFood("Món lạ", 120.0, 0.4)])
    assert items[0].resolved is False
    assert items[0].weight_grams == 120
    assert items[0].calories == 0


def test_totals_ignore_nothing():
    items = resolve(
        [RecognizedFood("Cơm trắng", 100.0, 0.9), RecognizedFood("Phở bò", 100.0, 0.9)]
    )
    assert total(items).calories == 220


# MARK: prompt parsing


def test_parser_tolerates_a_json_fence():
    text = '```json\n{"foods":[{"name":"Phở bò","estimatedWeightGrams":400,"confidence":0.9}]}\n```'
    foods = parse_recognition_json(text)
    assert foods[0].name == "Phở bò"
    assert foods[0].estimated_weight_grams == 400


def test_parser_folds_percentage_confidence_back_to_a_fraction():
    text = '{"foods":[{"name":"Phở bò","estimatedWeightGrams":400,"confidence":92}]}'
    assert parse_recognition_json(text)[0].confidence == pytest.approx(0.92)


def test_parser_rejects_non_json_loudly():
    with pytest.raises(ProviderError):
        parse_recognition_json("I think this is a bowl of pho.")
