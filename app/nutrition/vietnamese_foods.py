"""A Vietnamese food table, per plan.md §10.

Figures are per 100 g of the dish **as served** and are **approximate reference
values**, not a certified nutrition database. They are here so the pipeline is
exercisable end to end; USDA and Open Food Facts are the Phase 3 replacements.
Anything shipped to real users should come from a sourced database, not this
file.

Two things about the numbers, so they are not mistaken for more than they are:

- Broth dishes are *dilute*. Phở is ~90 kcal/100 g because most of a bowl is
  liquid, while a rice plate is ~150–190. A 650 g bowl and a 250 g plate can
  therefore land in the same place, which is why the model is asked for grams of
  the dish rather than of its parts.
- Each row is roughly self-consistent under 4/4/9 kcal per gram of
  protein/carbohydrate/fat. Where it is not, the calorie figure wins — it is the
  one the user sees.

Lookup is exact, never fuzzy (see `lookup`), so **coverage comes from rows and
aliases, not from guessing**. The keys are base dish names because that is what
`RECOGNITION_PROMPT` asks the model for; a row keyed "Phở bò tái chín" would
help nobody.
"""

import unicodedata
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
    #: Alternate spellings the model may produce, per plan.md §10. Accent-only
    #: variants do not need listing — `_key` strips accents.
    aliases: List[str] = field(default_factory=list)


FOODS: List[FoodNutrition] = [
    # Noodle soups — mostly broth, so the density is low
    FoodNutrition("Phở bò", "Beef pho", 90, 6.0, 12.0, 1.8, ["pho bo", "pho", "phở"]),
    FoodNutrition("Phở gà", "Chicken pho", 85, 6.5, 11.0, 1.5),
    FoodNutrition("Bún bò Huế", "Spicy beef noodle soup", 105, 7.0, 13.0, 2.6, ["bún bò"]),
    FoodNutrition("Hủ tiếu", "Hu tieu noodle soup", 95, 5.5, 14.0, 1.8, ["hu tieu"]),
    FoodNutrition("Mì Quảng", "Mi Quang noodles", 120, 7.0, 16.0, 3.0),
    FoodNutrition("Bún riêu", "Crab noodle soup", 80, 5.0, 10.0, 2.0, ["bún riêu cua"]),
    FoodNutrition("Bún cá", "Fish noodle soup", 90, 6.5, 11.0, 1.8),
    FoodNutrition("Bánh canh", "Thick noodle soup", 100, 5.5, 15.0, 2.0),
    FoodNutrition("Miến gà", "Chicken glass noodle soup", 85, 6.0, 12.0, 1.2),
    FoodNutrition("Bún mắm", "Fermented fish noodle soup", 100, 6.0, 13.0, 2.5),
    FoodNutrition("Cháo gà", "Chicken rice porridge", 70, 4.0, 10.0, 1.5, ["cháo"]),
    FoodNutrition("Cháo lòng", "Offal rice porridge", 90, 5.0, 11.0, 3.0),
    FoodNutrition("Lẩu", "Hotpot", 80, 6.0, 5.0, 4.0),
    # Rice dishes
    FoodNutrition("Cơm trắng", "White rice", 130, 2.7, 28.0, 0.3, ["com trang", "rice", "cơm"]),
    FoodNutrition("Cơm tấm", "Broken rice", 150, 3.0, 31.0, 1.2, ["com tam", "broken rice"]),
    FoodNutrition("Cơm gà", "Chicken rice", 165, 9.5, 24.0, 3.5, ["com ga", "chicken rice"]),
    FoodNutrition("Cơm rang", "Fried rice", 185, 6.0, 28.0, 5.5, ["cơm chiên", "fried rice"]),
    FoodNutrition("Cơm sườn", "Rice with pork chop", 190, 10.0, 26.0, 5.5),
    FoodNutrition("Cơm bò", "Rice with beef", 175, 11.0, 23.0, 4.5),
    FoodNutrition("Cơm cá", "Rice with fish", 160, 11.0, 22.0, 3.0),
    FoodNutrition("Xôi", "Sticky rice", 200, 4.5, 40.0, 2.5),
    FoodNutrition("Xôi xéo", "Sticky rice with mung bean", 230, 6.0, 38.0, 6.0),
    # Stir-fried noodles
    FoodNutrition("Bún thịt nướng", "Grilled pork noodles", 160, 9.0, 21.0, 4.5, ["bun thit nuong"]),
    FoodNutrition("Bún đậu", "Noodles with tofu", 170, 9.0, 20.0, 6.0, ["bún đậu mắm tôm"]),
    FoodNutrition("Mì xào", "Stir-fried noodles", 180, 7.0, 25.0, 5.5),
    FoodNutrition("Phở xào", "Stir-fried flat noodles", 190, 8.0, 26.0, 6.0),
    FoodNutrition("Mì gói", "Instant noodles, cooked", 110, 3.0, 15.0, 4.5, ["mì ăn liền"]),
    # Bánh
    FoodNutrition("Bánh mì thịt", "Banh mi", 250, 11.0, 33.0, 8.0, ["banh mi", "bánh mì"]),
    FoodNutrition("Bánh mì trứng", "Banh mi with egg", 240, 10.0, 32.0, 8.0),
    FoodNutrition("Bánh mì chả", "Banh mi with pork roll", 260, 10.0, 34.0, 9.0),
    FoodNutrition("Bánh cuốn", "Steamed rice roll", 120, 5.0, 20.0, 2.2, ["banh cuon"]),
    FoodNutrition("Bánh xèo", "Sizzling pancake", 210, 7.0, 22.0, 11.0, ["banh xeo"]),
    FoodNutrition("Bánh khọt", "Mini savoury pancakes", 200, 6.0, 21.0, 10.0),
    FoodNutrition("Bánh bèo", "Steamed rice cakes", 130, 3.5, 24.0, 2.5),
    FoodNutrition("Bánh giò", "Pyramid rice dumpling", 160, 5.0, 22.0, 6.0),
    FoodNutrition("Bánh bao", "Steamed bun", 220, 8.0, 33.0, 6.0),
    FoodNutrition("Bánh chưng", "Square sticky rice cake", 220, 5.0, 38.0, 5.0),
    FoodNutrition("Bánh tét", "Cylindrical sticky rice cake", 210, 4.5, 37.0, 4.5),
    # Rolls and pork products
    FoodNutrition("Chả giò", "Spring roll", 290, 9.0, 26.0, 16.0, ["cha gio", "nem rán", "spring roll"]),
    FoodNutrition("Gỏi cuốn", "Fresh spring roll", 95, 6.0, 14.0, 1.0, ["goi cuon", "summer roll"]),
    FoodNutrition("Nem nướng", "Grilled pork sausage", 230, 16.0, 8.0, 16.0),
    FoodNutrition("Chả lụa", "Vietnamese pork roll", 200, 14.0, 2.0, 15.0, ["chả"]),
    FoodNutrition("Chả cá", "Fried fish cake", 180, 16.0, 6.0, 10.0),
    # Grilled, braised and fried mains
    FoodNutrition("Sườn nướng", "Grilled pork chop", 240, 22.0, 3.0, 15.0, ["suon nuong", "grilled pork"]),
    FoodNutrition("Thịt heo nướng", "Grilled pork", 240, 22.0, 4.0, 15.0, ["thịt nướng"]),
    FoodNutrition("Thịt bò nướng", "Grilled beef", 210, 26.0, 2.0, 11.0),
    FoodNutrition("Bò lúc lắc", "Shaking beef", 200, 20.0, 6.0, 11.0),
    FoodNutrition("Bò kho", "Braised beef", 180, 15.0, 6.0, 11.0),
    FoodNutrition("Thịt kho tàu", "Braised pork belly with egg", 260, 16.0, 5.0, 20.0, ["thịt kho"]),
    FoodNutrition("Gà nướng", "Grilled chicken", 190, 25.0, 1.0, 9.0),
    FoodNutrition("Gà luộc", "Boiled chicken", 165, 25.0, 0.0, 7.0),
    FoodNutrition("Gà kho gừng", "Chicken braised with ginger", 200, 20.0, 5.0, 11.0),
    FoodNutrition("Vịt nướng", "Grilled duck", 240, 24.0, 1.0, 16.0),
    FoodNutrition("Cá nướng", "Grilled fish", 160, 22.0, 0.0, 7.5),
    FoodNutrition("Cá kho", "Braised fish", 170, 18.0, 4.0, 9.0),
    FoodNutrition("Tôm rang", "Sautéed prawns", 150, 18.0, 6.0, 6.0),
    FoodNutrition("Tôm nướng", "Grilled prawns", 100, 20.0, 1.0, 1.5, ["tôm"]),
    FoodNutrition("Mực xào", "Stir-fried squid", 120, 16.0, 5.0, 4.0),
    # Eggs and tofu
    FoodNutrition("Trứng ốp la", "Fried egg", 196, 13.6, 0.8, 15.3, ["trung op la", "fried egg", "trứng"]),
    FoodNutrition("Trứng luộc", "Boiled egg", 155, 13.0, 1.1, 11.0),
    FoodNutrition("Trứng chiên", "Omelette", 180, 12.0, 1.0, 14.0),
    FoodNutrition("Đậu hũ", "Tofu", 145, 12.0, 4.0, 9.0, ["đậu phụ", "tofu"]),
    FoodNutrition("Đậu hũ sốt cà", "Tofu in tomato sauce", 120, 9.0, 6.0, 7.0),
    # Vegetables and soups
    FoodNutrition("Rau thơm", "Fresh herbs", 25, 2.2, 3.5, 0.4, ["rau thom", "herbs", "rau sống"]),
    FoodNutrition("Rau luộc", "Boiled vegetables", 25, 2.0, 4.0, 0.2),
    FoodNutrition("Rau muống xào", "Stir-fried water spinach", 90, 3.0, 6.0, 6.0, ["rau xào"]),
    FoodNutrition("Canh chua", "Sour soup", 45, 3.5, 5.0, 1.2),
    FoodNutrition("Canh rau", "Vegetable soup", 30, 1.5, 3.0, 1.2, ["canh"]),
    FoodNutrition("Dưa leo", "Cucumber", 15, 0.7, 3.6, 0.1, ["dưa chuột"]),
    FoodNutrition("Giá đỗ", "Bean sprouts", 30, 3.0, 4.0, 0.2, ["giá"]),
    FoodNutrition("Salad trộn", "Mixed salad", 60, 2.0, 6.0, 3.0, ["salad", "gỏi"]),
    # Fruit
    FoodNutrition("Chuối", "Banana", 89, 1.1, 23.0, 0.3),
    FoodNutrition("Xoài", "Mango", 60, 0.8, 15.0, 0.4),
    FoodNutrition("Dưa hấu", "Watermelon", 30, 0.6, 7.6, 0.2),
    FoodNutrition("Cam", "Orange", 47, 0.9, 12.0, 0.1),
    FoodNutrition("Táo", "Apple", 52, 0.3, 14.0, 0.2),
    FoodNutrition("Đu đủ", "Papaya", 43, 0.5, 11.0, 0.3),
    FoodNutrition("Thanh long", "Dragon fruit", 60, 1.2, 13.0, 0.4),
    FoodNutrition("Ổi", "Guava", 68, 2.6, 14.0, 1.0),
    # Sweets and drinks
    FoodNutrition("Sữa chua", "Yoghurt", 80, 3.5, 12.0, 1.8, ["sua chua", "yoghurt", "yogurt"]),
    FoodNutrition("Chè", "Sweet dessert soup", 150, 2.0, 30.0, 2.5),
    FoodNutrition("Bánh flan", "Crème caramel", 145, 4.0, 20.0, 5.0, ["kem flan"]),
    FoodNutrition("Kem", "Ice cream", 200, 3.5, 24.0, 10.0),
    FoodNutrition("Sinh tố", "Fruit smoothie", 90, 1.5, 18.0, 1.0),
    FoodNutrition("Cà phê sữa đá", "Iced coffee with milk", 80, 1.5, 14.0, 2.0, ["cà phê sữa"]),
    FoodNutrition("Trà sữa", "Milk tea", 90, 1.0, 17.0, 2.0),
    FoodNutrition("Nước mía", "Sugarcane juice", 60, 0.0, 15.0, 0.0),
    FoodNutrition("Sữa đậu nành", "Soy milk", 45, 3.0, 5.0, 1.5),
]


def _key(text: str) -> str:
    """Normalises for exact matching: case, whitespace and Vietnamese accents.

    Stripping accents is not fuzzy matching — "pho bo" and "Phở bò" are the same
    string written two ways, not two similar strings — and it is what lets one
    row absorb the accent-less spellings models produce, instead of an alias per
    variant. `đ` needs its own line because it is a distinct letter rather than a
    base plus a combining mark, so NFD leaves it whole.
    """
    lowered = " ".join(text.lower().split())
    without_marks = "".join(
        char
        for char in unicodedata.normalize("NFD", lowered)
        if not unicodedata.combining(char)
    )
    return without_marks.replace("đ", "d")


_INDEX: Dict[str, FoodNutrition] = {}
for _food in FOODS:
    _INDEX[_key(_food.name)] = _food
    _INDEX.setdefault(_key(_food.name_en), _food)
    for _alias in _food.aliases:
        _INDEX.setdefault(_key(_alias), _food)


def lookup(name: str) -> Optional[FoodNutrition]:
    """Exact match on name, English name or alias, ignoring case and accents.

    Deliberately not fuzzy: a near-miss that silently resolves to the wrong dish
    would produce confident, wrong calories. An unmatched food is surfaced to
    the user to correct instead — the client can accept nutrition by hand, so an
    unknown dish is answerable rather than a dead end.
    """
    return _INDEX.get(_key(name))
