"""Spike: derive a dish's per-100 g nutrition from USDA SR Legacy and a recipe.

`plan.md` §10 requires the 88-row Vietnamese table to be replaced by a licensed,
cited dataset before release. Surveying what exists turns up a wall:

- The **Vietnamese Food Composition Table** (Ministry of Health, 2017) is a
  302-page *printed book*. FAO lists it as print-only, with no download and no
  stated licence.
- **USDA FoodData Central** is CC0 public domain, downloadable in bulk with no
  API key — and contains **no Vietnamese dishes at all**. SR Legacy's 7,793 rows
  have rice, rice noodles, pork loin, beef round, shrimp, cilantro and french
  bread, but nothing called phở, and not even fish sauce.

That is not a licensing problem, it is a *shape* problem: national food
composition tables list **ingredients**, and a restaurant dish is not an
ingredient. No amount of licensing buys "Bún chả".

So the dish figures have to be **derived**: a recipe in grams over CC0
ingredient rows. The recipe is the editorial content this project writes and can
be argued with; every number under it is then traceable to an `fdcId` instead of
being asserted. That is what §10 actually asks for.

This is a **spike, not the replacement** — four dishes, to find out whether the
approach produces sane numbers before anyone rewrites `vietnamese_foods.py`. See
tools/eval/README.md for what it found.

    curl -O https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip
    unzip FoodData_Central_sr_legacy_food_json_2018-04.zip
    .venv/bin/python tools/nutrition/derive_from_usda.py FoodData_Central_sr_legacy_food_json_2018-04.json

The dump is 13 MB zipped / 210 MB unzipped and is **not committed**: it is
regenerable from a stable public URL, and a 210 MB blob in a repository this
size is worse than a download instruction.
"""

import json
import sys
from typing import Dict, List, Tuple

#: FoodData Central nutrient ids for the four figures this app tracks.
NUTRIENT_IDS = {1008: "kcal", 1003: "protein", 1005: "carb", 1004: "fat"}

#: Broth, modelled as water. It is most of a bowl of phở and carries almost
#: nothing, which is why a noodle soup lands near 90 kcal/100 g while a rice
#: plate lands near 150 — the observation `vietnamese_foods.py` already makes in
#: prose. Writing it as an ingredient makes it arguable instead of assumed, and
#: it is also the least certain number here: real bone broth is not water.
WATER = "water"

#: dish -> [(fdcId or WATER, grams in one serving)]
RECIPES: Dict[str, List[Tuple[object, float]]] = {
    "Phở bò": [
        (168914, 200),  # Rice noodles, cooked
        (168649, 60),  # Beef, round, top round steak, lean only, cooked
        (170005, 15),  # Onions, spring or scallions, raw
        (169997, 10),  # Coriander (cilantro) leaves, raw
        (WATER, 400),  # broth
    ],
    "Cơm tấm": [
        (168878, 250),  # Rice, white, long-grain, regular, enriched, cooked
        (168232, 90),  # Pork, fresh, loin, lean only, cooked, broiled
        (168409, 30),  # Cucumber, with peel, raw
    ],
    "Gỏi cuốn": [
        (168914, 45),
        (175180, 30),  # Crustaceans, shrimp, cooked
        (168232, 20),
        (168429, 20),  # Lettuce, butterhead, raw
        (172232, 10),  # Basil, fresh
        (168878, 15),
    ],
    "Bánh mì thịt": [
        (172675, 90),  # Bread, french or vienna
        (168232, 40),
        (172930, 15),  # Pate, goose liver, smoked, canned
        (168409, 20),
        (169997, 5),
        (171009, 8),  # Salad dressing, mayonnaise, regular
    ],
}

#: What `app/nutrition/vietnamese_foods.py` currently asserts, for comparison.
CURRENT = {
    "Phở bò": (90, 6.0, 12.0, 1.8),
    "Cơm tấm": (150, 3.0, 31.0, 1.2),
    "Gỏi cuốn": (95, 6.0, 14.0, 1.0),
    "Bánh mì thịt": (250, 11.0, 33.0, 8.0),
}


def load(path: str) -> Dict[int, dict]:
    with open(path, encoding="utf-8") as handle:
        return {food["fdcId"]: food for food in json.load(handle)["SRLegacyFoods"]}


def per_100g(food: dict) -> Dict[str, float]:
    values = {name: 0.0 for name in NUTRIENT_IDS.values()}
    for entry in food.get("foodNutrients", []):
        nutrient_id = entry.get("nutrient", {}).get("id")
        if nutrient_id in NUTRIENT_IDS and entry.get("amount") is not None:
            values[NUTRIENT_IDS[nutrient_id]] = entry["amount"]
    return values


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    foods = load(sys.argv[1])

    print(f"{'dish':<15}{'derived per 100 g':<36}{'current table':<32}{'Δ kcal':>7}")
    for dish, items in RECIPES.items():
        totals = {name: 0.0 for name in NUTRIENT_IDS.values()}
        grams = 0.0
        for fdc_id, weight in items:
            grams += weight
            if fdc_id == WATER:
                continue
            values = per_100g(foods[fdc_id])
            for key in totals:
                totals[key] += values[key] * weight / 100.0

        derived = {key: value / grams * 100 for key, value in totals.items()}
        current = CURRENT[dish]
        print(
            f"{dish:<15}"
            f"{derived['kcal']:6.0f} kcal {derived['protein']:5.1f}p "
            f"{derived['carb']:5.1f}c {derived['fat']:5.1f}f     "
            f"{current[0]:5.0f} kcal {current[1]:5.1f}p "
            f"{current[2]:5.1f}c {current[3]:5.1f}f  "
            f"{derived['kcal'] - current[0]:+7.0f}   ({grams:.0f} g serving)"
        )


if __name__ == "__main__":
    main()
