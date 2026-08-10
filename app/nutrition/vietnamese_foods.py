"""A small Vietnamese food table, per plan.md §10.

Figures are per 100 g and are **approximate reference values**, not a certified
nutrition database. They are here so the pipeline is exercisable end to end;
USDA and Open Food Facts are the Phase 3 replacements. Anything shipped to real
users should come from a sourced database, not this file.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class FoodNutrition:
    name: str
    name_en: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    #: Alternate spellings the model may produce, per plan.md §10.
    aliases: List[str] = field(default_factory=list)


FOODS: List[FoodNutrition] = [
    FoodNutrition("Cơm trắng", "White rice", 130, 2.7, 28.0, 0.3, ["com trang", "rice", "cơm"]),
    FoodNutrition("Cơm tấm", "Broken rice", 150, 3.0, 31.0, 1.2, ["com tam", "broken rice"]),
    FoodNutrition("Sườn nướng", "Grilled pork chop", 240, 22.0, 3.0, 15.0, ["suon nuong", "grilled pork"]),
    FoodNutrition("Trứng ốp la", "Fried egg", 196, 13.6, 0.8, 15.3, ["trung op la", "fried egg", "trứng"]),
    FoodNutrition("Phở bò", "Beef pho", 90, 6.0, 12.0, 1.8, ["pho bo", "pho", "phở"]),
    FoodNutrition("Bún bò Huế", "Spicy beef noodle soup", 105, 7.0, 13.0, 2.6, ["bun bo hue"]),
    FoodNutrition("Bánh mì thịt", "Banh mi", 250, 11.0, 33.0, 8.0, ["banh mi", "bánh mì"]),
    FoodNutrition("Bún thịt nướng", "Grilled pork noodles", 160, 9.0, 21.0, 4.5, ["bun thit nuong"]),
    FoodNutrition("Chả giò", "Spring roll", 290, 9.0, 26.0, 16.0, ["cha gio", "nem ran", "spring roll"]),
    FoodNutrition("Gỏi cuốn", "Fresh spring roll", 95, 6.0, 14.0, 1.0, ["goi cuon", "summer roll"]),
    FoodNutrition("Hủ tiếu", "Hu tieu noodle soup", 95, 5.5, 14.0, 1.8, ["hu tieu"]),
    FoodNutrition("Cơm gà", "Chicken rice", 165, 9.5, 24.0, 3.5, ["com ga", "chicken rice"]),
    FoodNutrition("Bánh cuốn", "Steamed rice roll", 120, 5.0, 20.0, 2.2, ["banh cuon"]),
    FoodNutrition("Bánh xèo", "Sizzling pancake", 210, 7.0, 22.0, 11.0, ["banh xeo"]),
    FoodNutrition("Rau thơm", "Fresh herbs", 25, 2.2, 3.5, 0.4, ["rau thom", "herbs", "rau sống"]),
    FoodNutrition("Sữa chua", "Yoghurt", 80, 3.5, 12.0, 1.8, ["sua chua", "yoghurt", "yogurt"]),
]


def _key(text: str) -> str:
    return " ".join(text.lower().split())


_INDEX: Dict[str, FoodNutrition] = {}
for _food in FOODS:
    _INDEX[_key(_food.name)] = _food
    _INDEX[_key(_food.name_en)] = _food
    for _alias in _food.aliases:
        _INDEX.setdefault(_key(_alias), _food)


def lookup(name: str) -> Optional[FoodNutrition]:
    """Exact match on name, English name or alias.

    Deliberately not fuzzy: a near-miss that silently resolves to the wrong dish
    would produce confident, wrong calories. An unmatched food is surfaced to
    the user to correct instead.
    """
    return _INDEX.get(_key(name))
