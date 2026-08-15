"""Adapter for the on-disk Vietnamese tables.

Two of them, and the order matters. `derived_foods.py` is generated from
`recipes.py` over CC0 USDA rows and carries the `fdcId`s it was computed from;
`vietnamese_foods.py` is the older hand-written table and is marked
`is_reference` because its figures are asserted rather than sourced.

**Derived wins.** A dish present in both is one that has been converted, and the
converted row is the better of the two by construction — it is the reason the
recipe was written. The reference table is what is left to convert, not a
fallback of equal standing, which is why `plan.md` §10's replacement can happen a
dish at a time instead of in one release.
"""

from typing import Optional

from .base import NutritionRecord, NutritionSource
from .derived_foods import lookup as derived_lookup
from .vietnamese_foods import lookup as reference_lookup


def _derived_record(name: str) -> Optional[NutritionRecord]:
    entry = derived_lookup(name)
    if entry is None:
        return None
    return NutritionRecord(
        name=entry.name,
        name_en=entry.name_en,
        calories_per_100g=entry.calories_per_100g,
        protein_per_100g=entry.protein_per_100g,
        carbs_per_100g=entry.carbs_per_100g,
        fat_per_100g=entry.fat_per_100g,
        source="usda_sr_legacy_recipe",
        # Every row the dish was computed from, so the figure is checkable rather
        # than merely attributed.
        source_id=",".join(str(fdc_id) for fdc_id in entry.source_ids),
        source_url="https://fdc.nal.usda.gov/",
        # Not a reference row: the nutrition behind it is measured and public
        # domain. What is still editorial is the *portions*, in `recipes.py`.
        is_reference=False,
    )


def _reference_record(name: str) -> Optional[NutritionRecord]:
    entry = reference_lookup(name)
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


def local_record(name: str, name_en: Optional[str] = None) -> Optional[NutritionRecord]:
    for candidate in (name, name_en):
        if not candidate:
            continue
        record = _derived_record(candidate)
        if record is not None:
            return record
    for candidate in (name, name_en):
        if not candidate:
            continue
        record = _reference_record(candidate)
        if record is not None:
            return record
    return None


class DerivedNutritionSource(NutritionSource):
    """Dishes with a recipe, computed from CC0 USDA rows.

    **Its own source so it can be ordered first**, which is the whole point.
    Under `usda,openfoodfacts,local` a deployed gateway resolved a 400 g bowl of
    phở to a packet of Shan Noodle instant soup — a real Open Food Facts product
    literally named "Beef Pho" at 367 kcal/100 g — and reported 1,467 kcal,
    because Open Food Facts was asked before the recipe was. For a dish the app
    has a recipe for, no barcode is a better answer than the recipe.
    """

    name = "derived"

    async def lookup(self, query: str) -> Optional[NutritionRecord]:
        return _derived_record(query)


class ReferenceNutritionSource(NutritionSource):
    """The hand-written rows that no recipe covers yet.

    Belongs **last**: its figures are asserted, so anything measured — USDA, or
    a packaged product that really is the food — should be preferred.
    """

    name = "reference"

    async def lookup(self, query: str) -> Optional[NutritionRecord]:
        return _reference_record(query)


class LocalNutritionSource(NutritionSource):
    """Both tables at one position in the chain, derived first.

    Kept because it is what existing configurations name, and because it is the
    right thing for a localhost gateway with no keys. A deployment that also
    uses USDA or Open Food Facts wants `derived,…,reference` instead, so that
    the asserted rows do not outrank measured ones and measured ones do not
    outrank a recipe.
    """

    name = "local"

    async def lookup(self, query: str) -> Optional[NutritionRecord]:
        return local_record(query)
