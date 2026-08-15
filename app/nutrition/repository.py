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
    return NutritionRepository([available[name] for name in requested])
