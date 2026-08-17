"""Ordered, fail-soft nutrition source composition."""

import logging
import os
from typing import Dict, List, Optional, Sequence

from .base import NutritionRecord, NutritionSource, NutritionSourceError
from .local import (
    DerivedNutritionSource,
    LocalNutritionSource,
    ReferenceNutritionSource,
)
from .open_food_facts import OpenFoodFactsSource
from .usda import USDAFoodDataSource

logger = logging.getLogger(__name__)


class NutritionRepository:
    def __init__(self, sources: Sequence[NutritionSource]) -> None:
        self.sources = list(sources)

    async def lookup(
        self, name: str, name_en: Optional[str] = None
    ) -> Optional[NutritionRecord]:
        for source in self.sources:
            if not source.is_configured:
                continue
            for query in source.queries(name, name_en):
                try:
                    record = await source.lookup(query)
                except NutritionSourceError as error:
                    # One provider outage must not discard a match from the next
                    # source. The warning remains visible in gateway logs.
                    logger.warning("nutrition source %s failed: %s", source.name, error)
                    break
                if record is not None:
                    return record
        return None

    def status(self) -> List[Dict[str, object]]:
        return [
            {"name": source.name, "configured": source.is_configured}
            for source in self.sources
        ]


def build_repository() -> NutritionRepository:
    available = {
        # `derived` and `reference` are the two halves of `local`, separable so
        # they can sit on either side of the network sources: a recipe should
        # beat a barcode, and an asserted row should not.
        "derived": DerivedNutritionSource(),
        "reference": ReferenceNutritionSource(),
        "local": LocalNutritionSource(),
        "usda": USDAFoodDataSource(),
        "openfoodfacts": OpenFoodFactsSource(),
    }
    requested = [
        name.strip().lower()
        for name in os.getenv("NUTRITION_SOURCES", "local").split(",")
        if name.strip()
    ]
    unknown = [name for name in requested if name not in available]
    if unknown:
        raise ValueError("Unknown nutrition source(s): {}".format(", ".join(unknown)))
    warn_if_barcodes_outrank_recipes(requested)
    return NutritionRepository([available[name] for name in requested])


#: Sources that answer out of someone else's catalogue rather than this
#: project's own recipes.
NETWORK_SOURCES = ("usda", "openfoodfacts")


def warn_if_barcodes_outrank_recipes(requested: Sequence[str]) -> None:
    """Says so, loudly, when the configured order is the one that has bitten twice.

    `.env.example` has carried the right order — `derived,usda,openfoodfacts,
    reference` — since the first incident: a bowl of phở resolved against a
    packaged "Beef Pho" at 367 kcal/100 g and reported 1.467 kcal. The example
    was fixed; **the deployed `.env` never was**, and a bowl of mì cay later
    came back at 3.000 kcal the same way.

    A comment in a file nobody reruns did not prevent the second one. This runs
    at startup against the configuration actually in force, which is the only
    place the mistake is visible.

    A warning rather than a refusal: the order is a judgement call, a deployment
    may have its reasons, and logging must never be the thing that takes a
    running gateway down. It is loud, it names the fix, and the logs carry
    timestamps to find it by.
    """
    recipe_positions = [
        requested.index(name) for name in ("derived", "local") if name in requested
    ]
    if not recipe_positions:
        return
    recipes_at = min(recipe_positions)
    outranking = [
        name
        for name in NETWORK_SOURCES
        if name in requested and requested.index(name) < recipes_at
    ]
    if not outranking:
        return
    logger.warning(
        "NUTRITION_SOURCES=%s puts %s ahead of this project's own recipes. A "
        "barcode will beat a recipe whenever both match, and a packaged "
        "product's per-100g is 'as sold' where a dish needs 'as served' — that "
        "is how a bowl of phở once reported 1.467 kcal and a bowl of mì cay "
        "3.000. Prefer NUTRITION_SOURCES=derived,usda,openfoodfacts,reference.",
        ",".join(requested),
        " and ".join(outranking),
    )
