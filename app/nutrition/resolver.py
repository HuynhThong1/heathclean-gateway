"""Turns recognized foods into nutrition.

This is where calories are decided — never in a provider. The model says "180 g
of cơm trắng"; this module says what that weighs in energy. Swapping the model
therefore cannot change the arithmetic (plan.md §2).
"""

from dataclasses import dataclass
import asyncio
from typing import List, Optional

from ..providers.base import RecognizedFood
from .base import NutritionRecord
from .local import local_record
from .repository import NutritionRepository


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


def _resolve_food(
    food: RecognizedFood, entry: Optional[NutritionRecord]
) -> ResolvedItem:
    if entry is None:
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

    ratio = food.estimated_weight_grams / 100.0
    return ResolvedItem(
        name=entry.name,
        name_en=entry.name_en,
        weight_grams=_round(food.estimated_weight_grams),
        calories=_round(entry.calories_per_100g * ratio, 0),
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
