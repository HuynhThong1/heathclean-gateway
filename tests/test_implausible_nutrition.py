"""The backstop against a figure that cannot be right.

Written from a real bowl of mì cay. The model named it in English — "Spicy
Noodle Soup" — which exactly matched a *packaged product* of that name in Open
Food Facts at 461 kcal/100 g. That is the density of the dry packet; the 650 g
the model estimated is the cooked bowl, most of which is broth. The client was
shown **3.000 kcal for a bowl of soup** with nothing to suggest it was wrong.

The mismatch is of units rather than of names — a barcode's per-100 g is "as
sold", a dish needs "as served" — and nothing in the data says which products
are sold dry. So the guard is on the arithmetic's own result.
"""

import logging

import pytest

from app.nutrition.base import NutritionRecord
from app.nutrition.repository import warn_if_barcodes_outrank_recipes
from app.nutrition.resolver import IMPLAUSIBLE_ITEM_CALORIES, resolve, _resolve_food
from app.providers.base import RecognizedFood


def food(name: str = "Mì cay", grams: float = 650) -> RecognizedFood:
    return RecognizedFood(
        name=name, name_en=None, estimated_weight_grams=grams, confidence=0.95
    )


def record(calories_per_100g: float, source: str = "open_food_facts") -> NutritionRecord:
    return NutritionRecord(
        name="Spicy Noodle Soup",
        name_en="Spicy Noodle Soup",
        calories_per_100g=calories_per_100g,
        protein_per_100g=9.2,
        carbs_per_100g=64.6,
        fat_per_100g=18.5,
        source=source,
    )


class TestTheCeiling:
    def test_the_bowl_that_caused_this_is_refused(self):
        """461 kcal/100 g × 650 g = 3.000. The exact figure that shipped."""
        item = _resolve_food(food(), record(461.5))

        assert item.resolved is False
        assert item.calories == 0
        assert item.nutrition_source is None

    def test_the_weight_survives_so_the_user_only_types_the_nutrition(self):
        item = _resolve_food(food(grams=650), record(461.5))

        assert item.weight_grams == 650
        assert item.name == "Mì cay"

    def test_the_heaviest_real_dish_still_passes(self):
        """Cơm sườn, the heaviest serving this project derives, at 699 kcal.

        A ceiling that rejected real food would be worse than the bug: it would
        push every large meal into manual entry.
        """
        item = _resolve_food(food("Cơm sườn", grams=341), record(205, "usda_sr_legacy_recipe"))

        assert item.resolved is True
        assert item.calories == 699

    def test_a_dense_food_in_a_small_portion_still_passes(self):
        """**Why the check is on the total and not on the density.**

        A 100 g bag of crisps really is 530 kcal/100 g, and that is a figure Open
        Food Facts gets right — packaged food is the one thing that database is
        for. A density ceiling would have to throw it away.
        """
        item = _resolve_food(food("Snack khoai tây", grams=100), record(530))

        assert item.resolved is True
        assert item.calories == 530

    def test_the_boundary_is_inclusive_of_the_ceiling(self):
        """Exactly at the limit is allowed; the guard is for what exceeds it."""
        grams = 100
        at_limit = _resolve_food(
            food(grams=grams), record(IMPLAUSIBLE_ITEM_CALORIES / grams * 100)
        )
        assert at_limit.resolved is True

    def test_an_unresolved_food_is_untouched_by_it(self):
        item = _resolve_food(food(), None)

        assert item.resolved is False
        assert item.calories == 0


class TestMiCay:
    def test_it_resolves_from_the_recipe_now(self):
        item = resolve([food("Mì cay", grams=650)])[0]

        assert item.resolved is True
        assert item.nutrition_source == "usda_sr_legacy_recipe"

    def test_a_bowl_is_a_meal_rather_than_a_day(self):
        """The bug in one assertion: a bowl of noodles is not 3.000 kcal."""
        item = resolve([food("Mì cay", grams=650)])[0]

        assert 400 < item.calories < 900

    def test_it_is_broth_light_the_way_a_soup_should_be(self):
        """A clay pot is mostly liquid, so it must not land near a rice plate."""
        from app.nutrition.local import local_record

        assert local_record("Mì cay").calories_per_100g < 150

    def test_the_generic_english_name_is_not_claimed(self):
        """Deliberately unresolved.

        A tom yum is also a spicy noodle soup. Claiming the phrase for mì cay
        would be the same over-reach as aliasing a combination dish onto one of
        its halves — and the fix for an English name is the prompt, not the
        table.
        """
        from app.nutrition.local import local_record

        assert local_record("Spicy Noodle Soup") is None


class Captured(logging.Handler):
    """Collects records from one logger, bypassing `caplog`.

    **`caplog` cannot see these.** `logging_config` sets `propagate: False` on
    the `app` logger — the standard uvicorn arrangement, so a message is not
    printed twice by the root handler as well — and pytest's `caplog` fixture
    works by attaching to the root. So the warning is emitted, is visible in the
    captured stderr, and never reaches `caplog.text`. Attaching here instead
    tests the logger that actually runs.
    """

    def __init__(self) -> None:
        super().__init__()
        self.messages: list = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())

    @property
    def text(self) -> str:
        return "\n".join(self.messages)


@pytest.fixture
def warnings_logged():
    logger = logging.getLogger("app.nutrition.repository")
    handler = Captured()
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


class TestSourceOrderWarning:
    def test_it_fires_when_barcodes_outrank_recipes(self, warnings_logged):
        """The order that shipped, and that `.env.example` has warned about since
        a bowl of phở reported 1.467 kcal."""
        warn_if_barcodes_outrank_recipes(["usda", "openfoodfacts", "local"])

        assert "ahead of this project's own recipes" in warnings_logged.text

    def test_it_names_the_order_to_use(self, warnings_logged):
        """A warning that does not say what to do instead gets ignored."""
        warn_if_barcodes_outrank_recipes(["usda", "openfoodfacts", "local"])

        assert "derived,usda,openfoodfacts,reference" in warnings_logged.text

    def test_it_is_silent_on_the_recommended_order(self, warnings_logged):
        warn_if_barcodes_outrank_recipes(
            ["derived", "usda", "openfoodfacts", "reference"]
        )

        assert warnings_logged.text == ""

    def test_reference_after_the_network_sources_is_fine(self, warnings_logged):
        """An *asserted* row should lose to a sourced one — only recipes should
        win. Warning about that would train people to ignore the warning."""
        warn_if_barcodes_outrank_recipes(["derived", "openfoodfacts", "reference"])

        assert warnings_logged.text == ""

    def test_a_local_only_deployment_says_nothing(self, warnings_logged):
        warn_if_barcodes_outrank_recipes(["local"])

        assert warnings_logged.text == ""
