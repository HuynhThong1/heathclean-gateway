"""Tests for the nutrition table itself, rather than for the endpoint."""

import pytest

from app.nutrition.vietnamese_foods import FOODS, lookup


def test_no_duplicate_dish_names():
    names = [food.name for food in FOODS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    "written",
    ["Phở bò", "phở bò", "  Phở   bò  ", "pho bo", "PHO BO", "Beef pho", "pho"],
)
def test_one_row_absorbs_case_spacing_accents_and_english(written):
    """Accent stripping is normalisation, not fuzzy matching — these are all the
    same string written differently, which is why one row can answer for all."""
    assert lookup(written).name == "Phở bò"


def test_d_with_stroke_is_normalised():
    """`đ` is its own letter, so NFD leaves it whole and it needs handling."""
    assert lookup("dau hu").name == "Đậu hũ"
    assert lookup("Đậu hũ").name == "Đậu hũ"


@pytest.mark.parametrize(
    "written", ["Phở bò tái chín", "Phở bò đặc biệt", "Cơm gà xối mỡ", "sushi"]
)
def test_a_near_miss_still_does_not_resolve(written):
    """The guarantee the table is built on: never silently answer for a dish
    that was not asked for. A preparation variant is a miss, and the client is
    expected to let the user supply nutrition instead."""
    assert lookup(written) is None


def test_calories_are_self_consistent_with_the_macros():
    """Each row should hold up under 4/4/9 kcal per gram. A row that drifts is a
    typo rather than a nuance at this level of precision."""
    drifted = []
    for food in FOODS:
        estimate = (
            food.protein_per_100g * 4 + food.carbs_per_100g * 4 + food.fat_per_100g * 9
        )
        if abs(estimate - food.calories_per_100g) > food.calories_per_100g * 0.25:
            drifted.append((food.name, food.calories_per_100g, round(estimate)))
    assert drifted == []


def test_broth_dishes_are_less_dense_than_rice_plates():
    """The distinction that makes gram estimates meaningful: a 650 g bowl of phở
    and a 250 g rice plate are not the same food at the same density."""
    assert lookup("Phở bò").calories_per_100g < lookup("Cơm tấm").calories_per_100g


def test_every_row_has_non_negative_figures():
    for food in FOODS:
        assert food.calories_per_100g >= 0
        assert min(food.protein_per_100g, food.carbs_per_100g, food.fat_per_100g) >= 0
