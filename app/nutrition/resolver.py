"""Turns recognized foods into nutrition.

This is where calories are decided — never in a provider. The model says "180 g
of cơm trắng"; this module says what that weighs in energy. Swapping the model
therefore cannot change the arithmetic (plan.md §2).
"""

from dataclasses import dataclass
from typing import List, Optional

from ..providers.base import RecognizedFood
from .vietnamese_foods import lookup


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


def _round(value: float, places: int = 1) -> float:
    return round(value + 0.0, places)


def resolve(foods: List[RecognizedFood]) -> List[ResolvedItem]:
    items: List[ResolvedItem] = []
    for food in foods:
        entry = lookup(food.name)
        if entry is None and food.name_en:
            entry = lookup(food.name_en)

        if entry is None:
            items.append(
                ResolvedItem(
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
            )
            continue

        ratio = food.estimated_weight_grams / 100.0
        items.append(
            ResolvedItem(
                name=entry.name,
                name_en=entry.name_en,
                weight_grams=_round(food.estimated_weight_grams),
                calories=_round(entry.calories_per_100g * ratio, 0),
                protein=_round(entry.protein_per_100g * ratio),
                carbs=_round(entry.carbs_per_100g * ratio),
                fat=_round(entry.fat_per_100g * ratio),
                confidence=food.confidence,
                resolved=True,
            )
        )
    return items


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
