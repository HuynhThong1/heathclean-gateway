"""Turn `app/nutrition/recipes.py` into the generated `derived_foods.py`.

    python tools/nutrition/generate_derived.py <SR Legacy json>            # print
    python tools/nutrition/generate_derived.py <SR Legacy json> --write    # write

The SR Legacy dump is 13 MB zipped / 210 MB unzipped and is **not committed** —
it is regenerable from a stable public URL, and the generated file is the part
this repository needs at runtime:

    curl -O https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip
    unzip FoodData_Central_sr_legacy_food_json_2018-04.zip

Everything USDA publishes is CC0 public domain; attribution is requested rather
than required, and the generated header carries it.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.nutrition.recipes import RECIPES, WATER, Recipe  # noqa: E402

OUTPUT = REPO_ROOT / "app" / "nutrition" / "derived_foods.py"

#: FoodData Central nutrient ids for the four figures this app tracks.
NUTRIENT_IDS = {1008: "calories", 1003: "protein", 1005: "carbs", 1004: "fat"}

HEADER = '''"""Vietnamese dishes with nutrition derived from USDA FoodData Central.

**Generated — do not edit.** Change `recipes.py` and re-run:

    python tools/nutrition/generate_derived.py <SR Legacy json> --write

Nutrition per 100 g of the dish as served, computed from a serving written in
`recipes.py` over rows of USDA FoodData Central SR Legacy (April 2018), which is
CC0 public domain. `source_ids` is every row that went into the dish, so any
figure here can be checked against
https://fdc.nal.usda.gov/food-details/<id>/nutrients.

These rows are **not** `is_reference`: the nutrition behind them is measured and
public-domain. The uncertainty that remains is in the *portions* — how much
noodle, how much broth — which is `recipes.py`'s editorial judgement and is
where a reader should look before trusting a number.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .vietnamese_foods import _key


@dataclass(frozen=True)
class DerivedFood:
    name: str
    name_en: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    #: Every FoodData Central row the dish was computed from.
    source_ids: Tuple[int, ...]
    #: Grams of one serving, which is what the per-100 g figures were divided by.
    serving_grams: float
    aliases: List[str] = field(default_factory=list)


DERIVED: List[DerivedFood] = [
'''

FOOTER = ''']


_INDEX: Dict[str, DerivedFood] = {}
for _food in DERIVED:
    for _name in [_food.name, _food.name_en, *_food.aliases]:
        _INDEX.setdefault(_key(_name), _food)


def lookup(name: str) -> Optional[DerivedFood]:
    """Exact match on a normalized name, never a fuzzy guess.

    Shares `_key` with the reference table so the two agree about what counts as
    the same name — a dish resolving from one source and missing from the other
    on spelling alone would be the worst of both.
    """
    return _INDEX.get(_key(name))
'''


def load_foods(path: str) -> Dict[int, dict]:
    with open(path, encoding="utf-8") as handle:
        return {food["fdcId"]: food for food in json.load(handle)["SRLegacyFoods"]}


def per_100g(food: dict) -> Dict[str, float]:
    values = {name: 0.0 for name in NUTRIENT_IDS.values()}
    for entry in food.get("foodNutrients", []):
        nutrient_id = entry.get("nutrient", {}).get("id")
        if nutrient_id in NUTRIENT_IDS and entry.get("amount") is not None:
            values[NUTRIENT_IDS[nutrient_id]] = entry["amount"]
    return values


def derive(recipe: Recipe, foods: Dict[int, dict]) -> Tuple[Dict[str, float], float, List[int]]:
    totals = {name: 0.0 for name in NUTRIENT_IDS.values()}
    grams = 0.0
    ids: List[int] = []

    for item in recipe.ingredients:
        grams += item.grams
        if item.fdc_id == WATER:
            continue
        food = foods.get(item.fdc_id)
        if food is None:
            raise SystemExit(
                f"{recipe.name}: fdcId {item.fdc_id} is not in this SR Legacy dump"
            )
        ids.append(item.fdc_id)
        values = per_100g(food)
        for key in totals:
            totals[key] += values[key] * item.grams / 100.0

    if grams <= 0:
        raise SystemExit(f"{recipe.name}: a serving cannot weigh nothing")
    return {key: value / grams * 100 for key, value in totals.items()}, grams, ids


def render(rows: List[Tuple[Recipe, Dict[str, float], float, List[int]]]) -> str:
    lines = [HEADER]
    for recipe, values, grams, ids in rows:
        aliases = ", ".join(f'"{alias}"' for alias in recipe.aliases)
        lines.append(
            f'    DerivedFood(\n'
            f'        "{recipe.name}",\n'
            f'        "{recipe.name_en}",\n'
            f'        {values["calories"]:.0f},\n'
            f'        {values["protein"]:.1f},\n'
            f'        {values["carbs"]:.1f},\n'
            f'        {values["fat"]:.1f},\n'
            f'        ({", ".join(str(i) for i in ids)},),\n'
            f'        {grams:.0f},\n'
            f'        [{aliases}],\n'
            f'    ),\n'
        )
    lines.append(FOOTER)
    return "".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", help="FoodData_Central_sr_legacy_food_json_*.json")
    parser.add_argument("--write", action="store_true", help=f"write {OUTPUT}")
    args = parser.parse_args()

    foods = load_foods(args.dump)
    rows = []
    for recipe in RECIPES:
        values, grams, ids = derive(recipe, foods)
        rows.append((recipe, values, grams, ids))
        print(
            f"{recipe.name:<16}{values['calories']:6.0f} kcal "
            f"{values['protein']:5.1f}p {values['carbs']:5.1f}c {values['fat']:5.1f}f"
            f"   ({grams:.0f} g serving)"
        )

    if args.write:
        OUTPUT.write_text(render(rows), encoding="utf-8")
        print(f"\nwrote {OUTPUT.relative_to(REPO_ROOT)} — {len(rows)} dishes")


if __name__ == "__main__":
    main()
