"""Adapter for the development-only Vietnamese reference table."""

from typing import Optional

from .base import NutritionRecord, NutritionSource
from .vietnamese_foods import lookup


def local_record(name: str, name_en: Optional[str] = None) -> Optional[NutritionRecord]:
    entry = lookup(name)
    if entry is None and name_en:
        entry = lookup(name_en)
    if entry is None:
        return None

    return NutritionRecord(
        name=entry.name,
        name_en=entry.name_en,
        calories_per_100g=entry.calories_per_100g,
        protein_per_100g=entry.protein_per_100g,
        carbs_per_100g=entry.carbs_per_100g,
        fat_per_100g=entry.fat_per_100g,
        source="local_reference",
        source_id=entry.name,
        is_reference=True,
    )


class LocalNutritionSource(NutritionSource):
    name = "local"

    async def lookup(self, query: str) -> Optional[NutritionRecord]:
        return local_record(query)
