"""Turns recognized foods into nutrition.

This is where calories are decided — never in a provider. The model says "180 g
of cơm trắng"; this module says what that weighs in energy. Swapping the model
therefore cannot change the arithmetic (plan.md §2).
"""

from dataclasses import dataclass
import asyncio
import logging
import os
from typing import List, Optional

from ..providers.base import RecognizedFood
from .base import NutritionRecord
from .local import local_record
from .repository import NutritionRepository

logger = logging.getLogger(__name__)

#: No single dish is worth more than this, and one that computes higher is an
#: error rather than a big lunch.
#:
#: **The check is on the dish's total, not on its density**, and that is the
#: design. A ceiling on kcal/100 g would have to reject a 100 g bag of crisps at
#: 530 — a figure Open Food Facts gets *right*, and the one case that database
#: is actually for. What is never right is a single item coming to three
#: thousand calories.
#:
#: 1.200 is grounded rather than picked: the heaviest serving this project
#: derives is Cơm sườn at 699 kcal, and the densest dish is Chả giò at 319
#: kcal/100 g. The ceiling sits well above the heaviest real dish, so a
#: genuinely large portion still passes.
IMPLAUSIBLE_ITEM_CALORIES = float(os.getenv("MAX_ITEM_CALORIES", "1200"))


@dataclass(frozen=True)
class ResolvedItem:
    name: str
    name_en: Optional[str]
    weight_grams: float
    calories: float
    protein: float
    carbs: float
    fat: float
    confidence: float
    #: False when the food was not in the database. Weight is kept, nutrition is
    #: zero, and the client must ask the user rather than pretend.
    resolved: bool
    nutrition_source: Optional[str] = None
    nutrition_source_id: Optional[str] = None
    nutrition_source_url: Optional[str] = None
    nutrition_is_reference: bool = False


def _round(value: float, places: int = 1) -> float:
    return round(value + 0.0, places)


def _unresolved(food: RecognizedFood) -> ResolvedItem:
    """Weight kept, nutrition zero, `resolved=False` — the client asks the user."""
    return ResolvedItem(
        name=food.name,
        name_en=food.name_en,
        weight_grams=_round(food.estimated_weight_grams),
        calories=0.0,
        protein=0.0,
        carbs=0.0,
        fat=0.0,
        confidence=food.confidence,
        resolved=False,
    )


def _resolve_food(
    food: RecognizedFood, entry: Optional[NutritionRecord]
) -> ResolvedItem:
    if entry is None:
        return _unresolved(food)

    ratio = food.estimated_weight_grams / 100.0

    # A figure that cannot be right must not be presented as one.
    #
    # This exists because of a real bowl of mì cay. The model named it in
    # English — "Spicy Noodle Soup" — which matched a **packaged product** of
    # that exact name in Open Food Facts at 461 kcal/100 g. That is the density
    # of the *dry packet*; the model's 650 g is the weight of the *cooked bowl*,
    # most of which is broth. Multiplying one by the other gave 3.000 kcal for a
    # bowl of soup, and the client had no way to know it was nonsense.
    #
    # The mismatch is of units, not of names: a barcode's per-100 g is "as
    # sold", and this app needs "as served". Detecting that in general means
    # knowing which products are sold dry, which is not in the data — so the
    # backstop is the arithmetic's own result, checked against what a dish can
    # weigh in energy.
    #
    # Falling back to *unresolved* rather than to a guess is the same rule the
    # rest of this module follows: over-counting a meal by four times is worse
    # than asking, because it silently blows the user's day budget and every
    # figure downstream of it.
    calories = entry.calories_per_100g * ratio
    if calories > IMPLAUSIBLE_ITEM_CALORIES:
        logger.warning(
            "implausible nutrition for %r: %.0f kcal from %s (%.0f kcal/100g x %.0f g) "
            "— treating as unresolved",
            food.name,
            calories,
            entry.source,
            entry.calories_per_100g,
            food.estimated_weight_grams,
        )
        return _unresolved(food)

    return ResolvedItem(
        name=entry.name,
        name_en=entry.name_en,
        weight_grams=_round(food.estimated_weight_grams),
        calories=_round(calories, 0),
        protein=_round(entry.protein_per_100g * ratio),
        carbs=_round(entry.carbs_per_100g * ratio),
        fat=_round(entry.fat_per_100g * ratio),
        confidence=food.confidence,
        resolved=True,
        nutrition_source=entry.source,
        nutrition_source_id=entry.source_id,
        nutrition_source_url=entry.source_url,
        nutrition_is_reference=entry.is_reference,
    )


def resolve(foods: List[RecognizedFood]) -> List[ResolvedItem]:
    """Synchronous local resolver retained for unit tests and simple tooling."""
    return [_resolve_food(food, local_record(food.name, food.name_en)) for food in foods]


async def resolve_with_repository(
    foods: List[RecognizedFood], repository: NutritionRepository
) -> List[ResolvedItem]:
    entries = await asyncio.gather(
        *(repository.lookup(food.name, food.name_en) for food in foods)
    )
    return [_resolve_food(food, entry) for food, entry in zip(foods, entries)]


@dataclass(frozen=True)
class Totals:
    calories: float
    protein: float
    carbs: float
    fat: float


def total(items: List[ResolvedItem]) -> Totals:
    return Totals(
        calories=_round(sum(item.calories for item in items), 0),
        protein=_round(sum(item.protein for item in items)),
        carbs=_round(sum(item.carbs for item in items)),
        fat=_round(sum(item.fat for item in items)),
    )
