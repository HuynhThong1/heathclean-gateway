import asyncio

import httpx

from app.nutrition.base import NutritionSource, NutritionSourceError
from app.nutrition.local import LocalNutritionSource
from app.nutrition.open_food_facts import OpenFoodFactsSource
from app.nutrition.repository import NutritionRepository
from app.nutrition.usda import USDAFoodDataSource


def test_local_rows_are_explicitly_marked_as_unsourced_reference_data():
    record = asyncio.run(LocalNutritionSource().lookup("Phở bò"))

    assert record.source == "local_reference"
    assert record.is_reference is True
    assert record.source_url is None


def test_one_source_outage_falls_through_to_the_next_source():
    class BrokenSource(NutritionSource):
        name = "broken"

        async def lookup(self, query):
            raise NutritionSourceError("offline")

    repository = NutritionRepository([BrokenSource(), LocalNutritionSource()])
    record = asyncio.run(repository.lookup("Phở bò", "Beef pho"))

    assert record.source == "local_reference"


def test_usda_uses_an_exact_token_match_and_keeps_provenance():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/foods/search")
        return httpx.Response(
            200,
            json={
                "foods": [
                    {
                        "fdcId": 328637,
                        "description": "Cheese, cheddar",
                        "foodNutrients": [
                            {"nutrientId": 1008, "value": 408},
                            {"nutrientId": 1003, "value": 23.3},
                            {"nutrientId": 1005, "value": 2.44},
                            {"nutrientId": 1004, "value": 34.0},
                        ],
                    }
                ]
            },
        )

    source = USDAFoodDataSource(
        api_key="test-key", transport=httpx.MockTransport(handler)
    )
    record = asyncio.run(source.lookup("Cheddar cheese"))

    assert record.source == "usda_fdc"
    assert record.source_id == "328637"
    assert record.calories_per_100g == 408
    assert "328637" in record.source_url


def test_usda_does_not_accept_a_nearby_search_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "foods": [
                    {
                        "fdcId": 1,
                        "description": "Cheddar cheese spread",
                        "foodNutrients": [],
                    }
                ]
            },
        )

    source = USDAFoodDataSource(
        api_key="test-key", transport=httpx.MockTransport(handler)
    )
    assert asyncio.run(source.lookup("Cheddar cheese")) is None


def test_open_food_facts_requires_an_identifying_user_agent():
    source = OpenFoodFactsSource(user_agent="")
    assert source.is_configured is False
    assert asyncio.run(source.lookup("Nutella")) is None


def test_open_food_facts_reads_only_normalized_per_100g_values():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "HeathFirst/0.1 (team@example.com)"
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "code": "3017620422003",
                        "product_name": "Nutella",
                        "nutriments": {
                            "energy-kcal_100g": 539,
                            "proteins_100g": 6.3,
                            "carbohydrates_100g": 57.5,
                            "fat_100g": 30.9,
                        },
                    }
                ]
            },
        )

    source = OpenFoodFactsSource(
        user_agent="HeathFirst/0.1 (team@example.com)",
        transport=httpx.MockTransport(handler),
    )
    record = asyncio.run(source.lookup("Nutella"))

    assert record.source == "open_food_facts"
    assert record.source_id == "3017620422003"
    assert record.calories_per_100g == 539
    assert record.is_reference is False
