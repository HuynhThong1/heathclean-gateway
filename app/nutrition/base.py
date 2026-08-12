"""Contracts shared by every nutrition data source.

Recognition providers only return a food name, grams and confidence. Sources
behind this contract return per-100 g nutrition plus provenance; the resolver
is the only layer that scales those values to the estimated serving.
"""

import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class NutritionRecord:
    name: str
    name_en: Optional[str]
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    source: str
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    #: True only for the unsourced development table. A client can surface this
    #: distinction instead of presenting an approximate row as authoritative.
    is_reference: bool = False


class NutritionSourceError(RuntimeError):
    """One source was unavailable or returned an unusable response."""


class NutritionSource(ABC):
    name: str = "unnamed"

    @property
    def is_configured(self) -> bool:
        return True

    @abstractmethod
    async def lookup(self, query: str) -> Optional[NutritionRecord]:
        """Return only a safe exact-name match, never a fuzzy guess."""
        raise NotImplementedError

    def queries(self, name: str, name_en: Optional[str]) -> Tuple[str, ...]:
        """Queries to try, in order.

        Local bilingual tables can cheaply try both. Network sources override
        this to make one request in their best-supported language.
        """
        return tuple(dict.fromkeys(value for value in (name, name_en) if value))


def name_signature(text: str) -> Tuple[str, ...]:
    """Case/accent/punctuation-insensitive token signature.

    Sorting lets `Cheddar cheese` match USDA's `Cheese, cheddar`, while token
    equality keeps `cheddar cheese spread` from silently becoming the same food.
    """
    lowered = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    without_marks = "".join(char for char in lowered if not unicodedata.combining(char))
    return tuple(sorted(re.findall(r"[a-z0-9]+", without_marks)))


def same_food_name(left: str, right: str) -> bool:
    signature = name_signature(left)
    return bool(signature) and signature == name_signature(right)
