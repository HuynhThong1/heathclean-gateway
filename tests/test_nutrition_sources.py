import asyncio

import httpx

from app.nutrition.base import NutritionRecord, NutritionSource, NutritionSourceError
from app.nutrition.local import (
    DerivedNutritionSource,
    LocalNutritionSource,
    ReferenceNutritionSource,
)
from app.nutrition.open_food_facts import OpenFoodFactsSource
from app.nutrition.repository import NutritionRepository
from app.nutrition.usda import USDAFoodDataSource


def test_a_converted_dish_comes_back_derived_and_cited():
    """Phở bò has a recipe, so it resolves from the generated table.

    The `fdcId`s are the point: a derived row can be checked against USDA, which
    is what takes it out of `is_reference`. What stays editorial is the portions
    in `recipes.py`, not the nutrition.
    """
    record = asyncio.run(LocalNutritionSource().lookup("Phở bò"))

    assert record.source == "usda_sr_legacy_recipe"
    assert record.is_reference is False
    assert record.source_id.split(",")[0].isdigit()


def an_unconverted_dish() -> str:
    """A reference row with no recipe yet — whichever one that is today.

    Found rather than hardcoded because the two tests using it pinned "Bánh
    chưng", and writing a recipe for it turned them both red. That is the wrong
    failure: a test for "unconverted rows are still marked unconverted" should
    not break *because* a row was converted, which is the work going right. It
    breaks when the table empties, and then both tests go with it.
    """
    from app.nutrition.derived_foods import lookup as derived_lookup
    from app.nutrition.vietnamese_foods import FOODS

    for entry in FOODS:
        if derived_lookup(entry.name) is None:
            return entry.name
    raise AssertionError(
        "every reference row now has a recipe — plan.md §10 is met, so "
        "vietnamese_foods.py and these two tests can go"
    )


def test_a_dish_still_awaiting_a_recipe_says_so():
    """Conversion is a dish at a time, so both tables are live at once.

    A row with no recipe yet keeps the old marking rather than borrowing the
    derived table's credibility.
    """
    record = asyncio.run(LocalNutritionSource().lookup(an_unconverted_dish()))

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

    assert record.source == "usda_sr_legacy_recipe"


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


def test_a_recipe_outranks_a_barcode_that_merely_shares_the_name():
    """The ordering bug that reached a deployed gateway.

    Open Food Facts has a product literally named "Beef Pho" — a packet of Shan
    Noodle instant soup at 367 kcal/100 g. Asked before the recipe, it turned a
    400 g bowl of phở into 1,467 kcal. `derived` exists so it can be ordered in
    front of every network source.
    """

    class PackagedNoodles(NutritionSource):
        name = "openfoodfacts"

        async def lookup(self, query):
            return NutritionRecord(
                name="Beef Pho",
                name_en="Beef Pho",
                calories_per_100g=367.0,
                protein_per_100g=5.0,
                carbs_per_100g=75.0,
                fat_per_100g=5.8,
                source="open_food_facts",
                source_id="0815055010023",
            )

    repository = NutritionRepository([DerivedNutritionSource(), PackagedNoodles()])
    record = asyncio.run(repository.lookup("Phở bò", "Beef pho"))

    assert record.source == "usda_sr_legacy_recipe"
    assert record.calories_per_100g < 120, "a bowl of phở is mostly broth"


def test_reference_rows_sit_last_so_measured_data_can_win():
    """`reference` on its own answers only what no recipe covers."""
    assert asyncio.run(ReferenceNutritionSource().lookup("Phở bò")) is not None
    assert asyncio.run(DerivedNutritionSource().lookup(an_unconverted_dish())) is None
