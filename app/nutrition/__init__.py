"""Nutrition lookup, source adapters and serving resolution."""

from .base import NutritionRecord, NutritionSource
from .repository import NutritionRepository, build_repository

__all__ = [
    "NutritionRecord",
    "NutritionRepository",
    "NutritionSource",
    "build_repository",
]
