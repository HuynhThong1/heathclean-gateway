"""Vietnamese dishes as recipes over USDA FoodData Central rows.

`plan.md` §10 requires the unsourced reference table to be replaced by a
licensed, cited dataset. There is no such dataset to buy, and that is not a
licensing problem:

- The **Vietnamese Food Composition Table** (Ministry of Health, 2017) is a
  302-page printed book. FAO lists it print-only, with no download and no
  stated licence.
- **USDA FoodData Central** is CC0 public domain and bulk-downloadable without
  an API key, and contains **no Vietnamese dishes at all**.

National food composition tables list *ingredients*. A restaurant dish is not an
ingredient, so no amount of licensing buys "Bún chả" — it has to be **derived**.
This file is the derivation: a serving in grams over public-domain rows. The
nutrition comes from USDA; the portions are the editorial judgement of this
project, and they are the part to argue with.

**What a reader should check.** Not the calories — those follow arithmetically
from the `fdc_id`s. Check the *grams*: whether 200 g of noodles and 380 g of
broth is the bowl you would be served, and whether the cut of meat named is the
cut that goes in. Every figure downstream is that judgement multiplied out.

Three modelling rules, each of which changed a number materially:

1. **Broth is not water.** Modelling a bowl's 380 g of broth as water put phở at
   47 kcal/100 g against a hand-written 90. `Soup, stock, chicken, home-prepared`
   (36 kcal/100 g) is the closest public-domain row to a simmered bone broth —
   canned bouillon, at 7, is a different liquid. Broth is the least certain
   number here and it dominates every soup.
2. **Cook the rice in the recipe, not before it.** USDA's cooked glutinous rice
   is boiled and very hydrated (97 kcal/100 g); xôi is *steamed* and dense. So
   xôi is written as dry rice plus the water it takes up, which lands near 175
   rather than 97.
3. **Frying oil is eaten.** A fried roll absorbs a good part of what it is fried
   in, and leaving it out understates the dish by a third.

Regenerate `derived_foods.py` after editing:

    python tools/nutrition/generate_derived.py <SR Legacy json> --write
"""

from dataclasses import dataclass, field
from typing import List

#: Water, and anything else that contributes mass but no energy — broth is *not*
#: this, see the module docstring. Counted in the serving weight, skipped in the
#: nutrition sum, which is what makes a dish's density come out right.
WATER = 0


@dataclass(frozen=True)
class Ingredient:
    #: FoodData Central id, or `WATER`.
    fdc_id: int
    grams: float
    #: What this row is standing in for, when the USDA description does not say.
    note: str = ""


@dataclass(frozen=True)
class Recipe:
    name: str
    name_en: str
    ingredients: List[Ingredient]
    #: Alternate spellings the model may produce. Accent-only variants do not
    #: need listing — lookup strips accents.
    aliases: List[str] = field(default_factory=list)
    #: Anything a reader should know before trusting the grams.
    note: str = ""


# Ingredient ids used more than once, named so a recipe reads as a recipe.
RICE_NOODLES = 168914  # Rice noodles, cooked
WHITE_RICE = 168878  # Rice, white, long-grain, regular, enriched, cooked
GLUTINOUS_RICE_DRY = 168883  # Rice, white, glutinous, unenriched, uncooked
EGG_NOODLES = 169732  # Noodles, egg, enriched, cooked
CELLOPHANE_NOODLES_DRY = 174258  # Noodles, chinese, cellophane (mung bean), dry
BEEF_ROUND = 168649  # Beef, top round steak, lean only, cooked
BEEF_GROUND = 174033  # Beef, ground, 85% lean, pan-broiled
PORK_LOIN = 168232  # Pork, fresh, loin, lean only, cooked, broiled
PORK_GROUND = 168374  # Pork, ground, 84% lean, cooked, pan-broiled
PORK_LEAN_GROUND = 168375  # Pork, ground, 96% lean, cooked, pan-broiled
PORK_BELLY = 167812  # Pork, fresh, belly, raw
PORK_RIBS = 167854  # Pork, fresh, spareribs, cooked, braised
CHICKEN_BREAST = 171477  # Chicken, breast, meat only, cooked, roasted
SHRIMP = 175180  # Crustaceans, shrimp, cooked
CRAB = 171966  # Crustaceans, crab, blue, canned
TOFU = 172475  # Tofu, raw, firm
EGG_BOILED = 173424  # Egg, whole, cooked, hard-boiled
EGG_FRIED = 173423  # Egg, whole, cooked, fried
FISH_SAUCE = 174531  # Sauce, fish, ready-to-serve
STOCK = 172884  # Soup, stock, chicken, home-prepared
SUGAR = 169655  # Sugars, granulated
OIL = 171411  # Oil, soybean, salad or cooking
BEAN_SPROUTS = 169957  # Mung beans, mature seeds, sprouted, raw
LETTUCE = 168429  # Lettuce, butterhead, raw
CUCUMBER = 168409  # Cucumber, with peel, raw
CARROT = 170393  # Carrots, raw
CILANTRO = 169997  # Coriander (cilantro) leaves, raw
BASIL = 172232  # Basil, fresh
SCALLION = 170005  # Onions, spring or scallions, raw
PEANUTS = 173806  # Peanuts, all types, dry-roasted, without salt
FRENCH_BREAD = 172675  # Bread, french or vienna
PATE = 172928  # Pate, chicken liver, canned
MAYONNAISE = 171009  # Salad dressing, mayonnaise, regular
RICE_FLOUR = 169714  # Rice flour, white, unenriched
WHEAT_FLOUR = 168894  # Wheat flour, white, all-purpose, enriched, bleached
MUSHROOM = 169251  # Mushrooms, white, raw
TOMATO = 170457  # Tomatoes, red, ripe, raw, year round average
LIME_JUICE = 168156  # Lime juice, raw
MUNG_BEANS = 174257  # Mung beans, mature seeds, cooked, boiled, without salt
TILAPIA = 175177  # Fish, tilapia, cooked, dry heat
DUCK = 172411  # Duck, domesticated, meat only, cooked, roasted
BEEF_CHUCK = 168667  # Beef, chuck, arm pot roast, lean and fat, braised
COCONUT_MILK = 170173  # Nuts, coconut milk, canned
TAPIOCA = 169717  # Tapioca, pearl, dry
BAMBOO = 169212  # Bamboo shoots, canned, drained solids
RICE_DRY = 168877  # Rice, white, long-grain, regular, raw, enriched
CATFISH = 173714  # Fish, catfish, channel, wild, cooked, dry heat
PORK_LIVER = 167863  # Pork, variety meats, liver, cooked, braised
CHITTERLINGS = 167856  # Pork, variety meats, chitterlings, cooked, simmered
FRIED_TOFU = 172451  # Tofu, fried
EGGPLANT = 169228  # Eggplant, raw
EGG_RAW = 171287  # Egg, whole, raw, fresh
WHOLE_MILK = 171265  # Milk, whole, 3.25% milkfat, with added vitamin D
CONDENSED_MILK = 171275  # Milk, canned, condensed, sweetened
YOGURT = 171284  # Yogurt, plain, whole milk
SOYMILK = 175215  # Soymilk (all flavors), unsweetened, with added calcium
COFFEE = 171890  # Beverages, coffee, brewed, prepared with tap water
CANE_SYRUP = 167743  # Syrup, cane
APPLE = 171688  # Apples, raw, with skin
WATERMELON = 167765  # Watermelon, raw
MANGO = 169910  # Mangos, raw
BANANA = 173944  # Bananas, raw
ORANGE = 169097  # Oranges, raw, all commercial varieties
PAPAYA = 169926  # Papayas, raw
GUAVA = 173044  # Guavas, common, raw
PAK_CHOI = 168517  # Cabbage, chinese (pak-choi), cooked, boiled, drained


RECIPES: List[Recipe] = [
    # ---- Noodle soups. Mostly broth, which is why they land near 70–110 while
    # a rice plate lands near 150. Bowl weights are 600–700 g.
    Recipe(
        "Phở bò",
        "Beef pho",
        [
            Ingredient(RICE_NOODLES, 200),
            Ingredient(BEEF_ROUND, 60, "thinly sliced rare beef"),
            Ingredient(STOCK, 380),
            Ingredient(BEAN_SPROUTS, 30),
            Ingredient(SCALLION, 15),
            Ingredient(CILANTRO, 10),
            Ingredient(FISH_SAUCE, 5),
        ],
        ["pho bo", "pho", "phở"],
    ),
    Recipe(
        "Phở gà",
        "Chicken pho",
        [
            Ingredient(RICE_NOODLES, 200),
            Ingredient(CHICKEN_BREAST, 60),
            Ingredient(STOCK, 380),
            Ingredient(SCALLION, 15),
            Ingredient(CILANTRO, 10),
            Ingredient(FISH_SAUCE, 5),
        ],
    ),
    Recipe(
        "Bún bò Huế",
        "Spicy beef noodle soup",
        [
            Ingredient(RICE_NOODLES, 200),
            Ingredient(BEEF_ROUND, 50),
            Ingredient(PORK_BELLY, 20, "raw weight; renders into the broth"),
            Ingredient(STOCK, 370),
            Ingredient(OIL, 6, "chilli oil"),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 8),
        ],
        ["bún bò"],
    ),
    Recipe(
        "Hủ tiếu",
        "Hu tieu noodle soup",
        [
            Ingredient(RICE_NOODLES, 180),
            Ingredient(PORK_LOIN, 40),
            Ingredient(SHRIMP, 25),
            Ingredient(STOCK, 350),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 5),
        ],
        ["hu tieu"],
    ),
    Recipe(
        "Bún riêu",
        "Crab noodle soup",
        [
            Ingredient(RICE_NOODLES, 180),
            Ingredient(CRAB, 40),
            Ingredient(TOFU, 30, "fried tofu"),
            Ingredient(TOMATO, 40),
            Ingredient(STOCK, 340),
            Ingredient(FISH_SAUCE, 6),
        ],
        ["bún riêu cua"],
    ),
    Recipe(
        "Mì Quảng",
        "Mi Quang noodles",
        [
            Ingredient(RICE_NOODLES, 180),
            Ingredient(PORK_LOIN, 40),
            Ingredient(SHRIMP, 25),
            Ingredient(PEANUTS, 10),
            Ingredient(STOCK, 150, "served barely wet, not as a soup"),
            Ingredient(OIL, 6),
            Ingredient(BASIL, 15),
        ],
        note="Deliberately little broth — a bowl of mì Quảng is closer to a "
        "dressed noodle than to phở, which is why it is denser than the soups.",
    ),
    Recipe(
        "Cháo gà",
        "Chicken rice porridge",
        [
            Ingredient(WHITE_RICE, 110),
            Ingredient(CHICKEN_BREAST, 40),
            Ingredient(STOCK, 350),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 4),
        ],
        ["cháo"],
    ),
    Recipe(
        "Miến gà",
        "Chicken glass noodle soup",
        [
            Ingredient(CELLOPHANE_NOODLES_DRY, 55, "dry weight"),
            Ingredient(WATER, 110, "absorbed on soaking"),
            Ingredient(CHICKEN_BREAST, 55),
            Ingredient(STOCK, 350),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 5),
        ],
        note="Glass noodles exist in USDA only dry, so the water they take up "
        "is written in — otherwise the bowl reads three times too dense.",
    ),
    # ---- Rice plates. The whole plate is weighed, so the meat has to be in it;
    # a row that models cơm tấm as rice alone under-reports protein by a third.
    Recipe(
        "Cơm trắng",
        "White rice",
        [Ingredient(WHITE_RICE, 250)],
        ["com trang", "rice", "cơm"],
    ),
    Recipe(
        "Cơm tấm",
        "Broken rice with grilled pork",
        [
            Ingredient(WHITE_RICE, 220),
            Ingredient(PORK_LOIN, 100, "sườn nướng"),
            Ingredient(OIL, 8, "mỡ hành"),
            Ingredient(CUCUMBER, 30),
            Ingredient(FISH_SAUCE, 12),
            Ingredient(SUGAR, 5),
        ],
        ["com tam", "broken rice"],
    ),
    Recipe(
        "Cơm gà",
        "Chicken rice",
        [
            Ingredient(WHITE_RICE, 220),
            Ingredient(CHICKEN_BREAST, 90),
            Ingredient(OIL, 6),
            Ingredient(CUCUMBER, 25),
        ],
        ["com ga", "chicken rice"],
    ),
    Recipe(
        "Cơm sườn",
        "Rice with pork ribs",
        [
            Ingredient(WHITE_RICE, 220),
            Ingredient(PORK_RIBS, 90),
            Ingredient(OIL, 6),
            Ingredient(CUCUMBER, 25),
        ],
    ),
    Recipe(
        "Cơm rang",
        "Fried rice",
        [
            Ingredient(WHITE_RICE, 250),
            Ingredient(EGG_FRIED, 50),
            Ingredient(OIL, 12),
            Ingredient(CARROT, 20),
            Ingredient(SCALLION, 10),
        ],
        ["cơm chiên", "fried rice"],
    ),
    Recipe(
        "Xôi",
        "Sticky rice",
        [
            Ingredient(GLUTINOUS_RICE_DRY, 85, "dry weight"),
            Ingredient(WATER, 95, "absorbed on steaming"),
        ],
        note="Written from dry rice because USDA's cooked glutinous rice is "
        "boiled and very wet (97 kcal/100 g). Steamed xôi is dense; this lands "
        "near 175, which is the dish.",
    ),
    # ---- Dry noodles and stir-fries.
    Recipe(
        "Bún thịt nướng",
        "Grilled pork noodles",
        [
            Ingredient(RICE_NOODLES, 180),
            Ingredient(PORK_LOIN, 70),
            Ingredient(PEANUTS, 8),
            Ingredient(LETTUCE, 30),
            Ingredient(CUCUMBER, 30),
            Ingredient(CARROT, 20),
            Ingredient(FISH_SAUCE, 20, "nước chấm"),
            Ingredient(SUGAR, 5),
            Ingredient(OIL, 5),
        ],
        ["bun thit nuong"],
    ),
    Recipe(
        "Bún thịt nướng chả giò",
        "Grilled pork noodles with fried spring rolls",
        [
            Ingredient(RICE_NOODLES, 180),
            # Less pork than the plain bowl's 70 g: the rolls carry part of the
            # protein, and a shop that adds them does not also serve a full
            # portion of grilled meat.
            Ingredient(PORK_LOIN, 55),
            # Two rolls, which is what a bowl comes with — the `Chả giò` recipe's
            # own serving scaled by about two thirds. Written out rather than
            # referenced, so the grams stay checkable in one place, which is what
            # this file asks a reader to check.
            Ingredient(RICE_FLOUR, 14, "chả giò wrappers"),
            Ingredient(PORK_GROUND, 27, "chả giò filling"),
            Ingredient(SHRIMP, 10, "chả giò filling"),
            Ingredient(CARROT, 10, "chả giò filling"),
            Ingredient(MUSHROOM, 7, "chả giò filling"),
            Ingredient(OIL, 12, "absorbed frying the rolls"),
            Ingredient(PEANUTS, 8),
            Ingredient(LETTUCE, 30),
            Ingredient(CUCUMBER, 30),
            Ingredient(CARROT, 20, "đồ chua on top"),
            Ingredient(FISH_SAUCE, 20, "nước chấm"),
            Ingredient(SUGAR, 5),
            Ingredient(OIL, 5, "marinade"),
        ],
        ["bun thit nuong cha gio", "bun thit nuong nem ran"],
        note="A row of its own rather than an alias of 'Bún thịt nướng', and "
        "that is the whole point of it. A Vietnamese menu lists this as one "
        "line, so the model names it as one — but aliasing it onto the plain "
        "bowl would price the whole serving at that dish's density and lose the "
        "rolls, which are more than twice as dense. Under-counting is what the "
        "unresolved state exists to prevent, so the combination is its own dish.",
    ),
    Recipe(
        "Bún chả",
        "Grilled pork with noodles",
        [
            Ingredient(RICE_NOODLES, 150),
            Ingredient(PORK_BELLY, 55, "raw weight, grilled"),
            Ingredient(PORK_GROUND, 30, "chả patties"),
            Ingredient(FISH_SAUCE, 25),
            Ingredient(WATER, 60, "the dipping bowl is diluted"),
            Ingredient(SUGAR, 8),
            Ingredient(CARROT, 20),
            Ingredient(LETTUCE, 30),
        ],
        ["bun cha"],
    ),
    Recipe(
        "Mì xào",
        "Stir-fried noodles",
        [
            Ingredient(EGG_NOODLES, 200),
            Ingredient(PORK_LOIN, 50),
            Ingredient(OIL, 12),
            Ingredient(CARROT, 30),
            Ingredient(MUSHROOM, 20),
            Ingredient(SCALLION, 10),
        ],
    ),
    Recipe(
        "Phở xào",
        "Stir-fried flat noodles",
        [
            Ingredient(RICE_NOODLES, 220),
            Ingredient(BEEF_ROUND, 60),
            Ingredient(OIL, 12),
            Ingredient(BEAN_SPROUTS, 40),
            Ingredient(SCALLION, 10),
        ],
    ),
    # ---- Bánh and bread.
    Recipe(
        "Bánh mì thịt",
        "Banh mi",
        [
            Ingredient(FRENCH_BREAD, 90),
            Ingredient(PORK_LOIN, 40),
            Ingredient(PATE, 15),
            Ingredient(MAYONNAISE, 8),
            Ingredient(CUCUMBER, 20),
            Ingredient(CARROT, 15),
            Ingredient(CILANTRO, 5),
        ],
        ["banh mi", "bánh mì"],
    ),
    Recipe(
        "Bánh cuốn",
        "Steamed rice roll",
        [
            Ingredient(RICE_FLOUR, 40),
            Ingredient(WATER, 120, "the batter is thin and steams into a sheet"),
            Ingredient(PORK_GROUND, 30),
            Ingredient(MUSHROOM, 15),
            Ingredient(FISH_SAUCE, 15),
        ],
        ["banh cuon"],
    ),
    Recipe(
        "Bánh xèo",
        "Sizzling pancake",
        [
            Ingredient(RICE_FLOUR, 45),
            Ingredient(WATER, 85),
            Ingredient(OIL, 15, "fried in a shallow pan; most of it is eaten"),
            Ingredient(PORK_LOIN, 30),
            Ingredient(SHRIMP, 30),
            Ingredient(BEAN_SPROUTS, 40),
        ],
        ["banh xeo"],
    ),
    Recipe(
        "Bánh bao",
        "Steamed bun",
        [
            Ingredient(WHEAT_FLOUR, 60),
            Ingredient(WATER, 35),
            Ingredient(PORK_GROUND, 35),
            Ingredient(EGG_BOILED, 15),
            Ingredient(MUSHROOM, 10),
        ],
    ),
    # ---- Rolls.
    Recipe(
        "Chả giò",
        "Fried spring roll",
        [
            Ingredient(RICE_FLOUR, 20, "wrappers"),
            Ingredient(PORK_GROUND, 40),
            Ingredient(SHRIMP, 15),
            Ingredient(CARROT, 15),
            Ingredient(MUSHROOM, 10),
            Ingredient(OIL, 18, "absorbed in the fryer"),
        ],
        ["cha gio", "nem rán", "spring roll"],
        note="The oil is the whole difference between this and gỏi cuốn. Leaving "
        "it out reads as a fresh roll.",
    ),
    Recipe(
        "Gỏi cuốn",
        "Fresh spring roll",
        [
            Ingredient(RICE_FLOUR, 12, "rice paper"),
            Ingredient(WATER, 12, "the paper is dipped before rolling"),
            Ingredient(RICE_NOODLES, 45),
            Ingredient(SHRIMP, 30),
            Ingredient(PORK_LOIN, 20),
            Ingredient(LETTUCE, 20),
            Ingredient(BASIL, 10),
        ],
        ["goi cuon", "summer roll"],
    ),
    # ---- Sides.
    Recipe(
        "Chả lụa",
        "Vietnamese pork roll",
        [
            Ingredient(PORK_LEAN_GROUND, 72, "the paste is lean pork, not mince"),
            Ingredient(PORK_BELLY, 14, "the fat that makes it bind"),
            Ingredient(WATER, 9, "ice water, beaten in"),
            Ingredient(FISH_SAUCE, 5),
        ],
        ["chả"],
        note="Written as lean paste plus fat rather than as ground pork: 84% "
        "mince puts it near 290 kcal/100 g, which is a sausage, not a giò.",
    ),
    Recipe(
        "Trứng chiên",
        "Fried egg",
        [
            Ingredient(EGG_FRIED, 60),
            Ingredient(OIL, 5),
            Ingredient(FISH_SAUCE, 3),
        ],
    ),
    Recipe(
        "Đậu hũ chiên",
        "Fried tofu",
        [
            Ingredient(TOFU, 100),
            Ingredient(OIL, 10),
        ],
    ),
    # ---- Dishes the reference table never had. These are the ones that make
    # the coverage figure move rather than only making it citable.
    Recipe(
        "Cao lầu",
        "Cao lau noodles",
        [
            Ingredient(EGG_NOODLES, 170, "the thick Hội An noodle"),
            Ingredient(PORK_LOIN, 60, "xá xíu"),
            Ingredient(STOCK, 120, "barely sauced, not a soup"),
            Ingredient(BEAN_SPROUTS, 30),
            Ingredient(BASIL, 15),
            Ingredient(OIL, 5),
        ],
        ["cao lau"],
    ),
    Recipe(
        "Xôi gà",
        "Sticky rice with chicken",
        [
            Ingredient(GLUTINOUS_RICE_DRY, 80, "dry weight"),
            Ingredient(WATER, 90, "absorbed on steaming"),
            Ingredient(CHICKEN_BREAST, 70),
            Ingredient(OIL, 5),
        ],
    ),
    Recipe(
        "Xôi xéo",
        "Sticky rice with mung bean",
        [
            Ingredient(GLUTINOUS_RICE_DRY, 80),
            Ingredient(WATER, 90),
            Ingredient(MUNG_BEANS, 45),
            Ingredient(OIL, 6, "mỡ hành"),
        ],
    ),
    Recipe(
        "Thịt kho tàu",
        "Braised pork with egg",
        [
            Ingredient(PORK_BELLY, 90, "raw weight"),
            Ingredient(EGG_BOILED, 50),
            Ingredient(COCONUT_MILK, 25, "nước dừa"),
            Ingredient(SUGAR, 8, "caramel"),
            Ingredient(FISH_SAUCE, 12),
            Ingredient(WATER, 60),
        ],
        ["thit kho", "thịt kho"],
    ),
    Recipe(
        "Bò kho",
        "Beef stew",
        [
            Ingredient(BEEF_CHUCK, 90),
            Ingredient(CARROT, 60),
            Ingredient(STOCK, 200),
            Ingredient(OIL, 6),
            Ingredient(FISH_SAUCE, 8),
        ],
        ["bo kho"],
    ),
    Recipe(
        "Canh chua",
        "Sour soup",
        [
            Ingredient(TILAPIA, 60),
            Ingredient(TOMATO, 50),
            Ingredient(BAMBOO, 30),
            Ingredient(STOCK, 300),
            Ingredient(SUGAR, 5),
            Ingredient(FISH_SAUCE, 8),
            Ingredient(LIME_JUICE, 8),
        ],
    ),
    Recipe(
        "Súp măng cua",
        "Crab and bamboo soup",
        [
            Ingredient(CRAB, 35),
            Ingredient(BAMBOO, 40),
            Ingredient(EGG_BOILED, 20, "stirred in as ribbons"),
            Ingredient(STOCK, 280),
            Ingredient(TAPIOCA, 8, "the starch that thickens it"),
        ],
    ),
    Recipe(
        "Bánh bột lọc",
        "Tapioca dumpling",
        [
            Ingredient(TAPIOCA, 45, "dry starch"),
            Ingredient(WATER, 55, "taken up in the dough"),
            Ingredient(SHRIMP, 25),
            Ingredient(PORK_BELLY, 12),
            Ingredient(FISH_SAUCE, 10),
        ],
        ["banh bot loc"],
    ),
    Recipe(
        "Bánh bèo",
        "Steamed rice cake",
        [
            Ingredient(RICE_FLOUR, 35),
            Ingredient(WATER, 105),
            Ingredient(SHRIMP, 15, "dried shrimp floss"),
            Ingredient(OIL, 4),
            Ingredient(FISH_SAUCE, 12),
        ],
    ),
    Recipe(
        "Bánh khọt",
        "Mini savoury pancakes",
        [
            Ingredient(RICE_FLOUR, 40),
            Ingredient(WATER, 70),
            Ingredient(COCONUT_MILK, 20),
            Ingredient(SHRIMP, 30),
            Ingredient(OIL, 14, "each mould is oiled"),
        ],
    ),
    Recipe(
        "Bún măng vịt",
        "Duck and bamboo noodle soup",
        [
            Ingredient(RICE_NOODLES, 180),
            Ingredient(DUCK, 60),
            Ingredient(BAMBOO, 40),
            Ingredient(STOCK, 340),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 6),
        ],
    ),
    Recipe(
        "Chả cá",
        "Turmeric fish with dill",
        [
            Ingredient(TILAPIA, 110),
            Ingredient(OIL, 14),
            Ingredient(SCALLION, 25),
            Ingredient(PEANUTS, 8),
            Ingredient(FISH_SAUCE, 8),
        ],
        ["chả cá Lã Vọng"],
    ),
    # ---- Dumplings. A whole family the tables had nothing for: a real scan of
    # sủi cảo came back unresolved at 95% confidence, which is the branch working
    # as designed and also a gap worth closing.
    Recipe(
        "Sủi cảo",
        "Dumpling soup",
        [
            Ingredient(WHEAT_FLOUR, 45, "wrappers"),
            Ingredient(WATER, 30, "taken up in the dough"),
            Ingredient(PORK_GROUND, 45),
            Ingredient(SHRIMP, 20),
            Ingredient(SCALLION, 10),
            Ingredient(STOCK, 250),
        ],
        ["sui cao", "há cảo", "ha cao"],
        note="Served in broth, which is why it is not as dense as a fried "
        "dumpling. `há cảo` is aliased here rather than given its own row: it is "
        "steamed and shrimp-heavy, close enough at this precision.",
    ),
    Recipe(
        "Hoành thánh",
        "Wonton soup",
        [
            Ingredient(WHEAT_FLOUR, 30, "thinner wrappers than sủi cảo"),
            Ingredient(WATER, 20),
            Ingredient(PORK_GROUND, 30),
            Ingredient(SHRIMP, 12),
            Ingredient(SCALLION, 10),
            Ingredient(STOCK, 300),
        ],
        ["hoanh thanh", "vằn thắn"],
    ),
    Recipe(
        "Mì vằn thắn",
        "Wonton egg noodle soup",
        [
            Ingredient(EGG_NOODLES, 120),
            Ingredient(WHEAT_FLOUR, 25, "wrappers"),
            Ingredient(WATER, 18),
            Ingredient(PORK_GROUND, 25),
            Ingredient(SHRIMP, 10),
            Ingredient(STOCK, 280),
            Ingredient(SCALLION, 10),
        ],
        ["mi van than", "mì hoành thánh"],
    ),
    Recipe(
        "Gỏi",
        "Vietnamese salad",
        [
            Ingredient(CARROT, 60),
            Ingredient(CUCUMBER, 60),
            Ingredient(SHRIMP, 40),
            Ingredient(PEANUTS, 12),
            Ingredient(FISH_SAUCE, 15),
            Ingredient(SUGAR, 6),
            Ingredient(LIME_JUICE, 8),
            Ingredient(BASIL, 10),
        ],
        ["gỏi tôm", "nộm"],
    ),
    # ---- Retiring the last of the asserted rows. Everything below was answered
    # by `vietnamese_foods.py` alone until now, which is the figure `plan.md` §10
    # is actually about: not how much resolves, but how much of what resolves is
    # sourced. The old asserted value is quoted beside each so the two can be
    # compared rather than silently swapped.
    Recipe(
        "Bánh canh",
        "Thick noodle soup",
        [
            Ingredient(TAPIOCA, 60, "the noodles are tapioca starch, not rice"),
            Ingredient(WATER, 120, "taken up in boiling"),
            Ingredient(PORK_RIBS, 45),
            Ingredient(SHRIMP, 20),
            Ingredient(STOCK, 330),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 6),
        ],
        ["banh canh", "bánh canh cua", "bánh canh giò heo"],
        note="A thicker, chewier noodle than phở's and a shorter bowl, so it "
        "lands above the rice-noodle soups rather than beside them. Asserted 100.",
    ),
    Recipe(
        "Bún cá",
        "Fish noodle soup",
        [
            Ingredient(RICE_NOODLES, 180),
            Ingredient(CATFISH, 60, "fried before it goes in"),
            Ingredient(OIL, 5, "absorbed frying the fish"),
            Ingredient(STOCK, 350),
            Ingredient(TOMATO, 30),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 6),
        ],
        ["bun ca", "bún cá rô"],
        note="Catfish stands in for the freshwater fish actually used (cá rô, "
        "cá lóc), which USDA does not carry. Asserted 90.",
    ),
    Recipe(
        "Bún đậu mắm tôm",
        "Rice noodles with fried tofu",
        [
            Ingredient(RICE_NOODLES, 150),
            Ingredient(FRIED_TOFU, 80),
            Ingredient(PORK_BELLY, 45, "raw weight; boiled and sliced"),
            Ingredient(CUCUMBER, 30),
            Ingredient(BASIL, 15),
            Ingredient(FISH_SAUCE, 10, "standing in for mắm tôm"),
        ],
        ["bun dau mam tom", "bún đậu"],
        note="A plate, not a bowl — no broth, which is why it is roughly twice "
        "the density of the soups. Fish sauce stands in for shrimp paste: both "
        "are salt and a little protein at this scale, and USDA has no mắm tôm. "
        "Asserted 170.",
    ),
    Recipe(
        "Bún mắm",
        "Fermented fish noodle soup",
        [
            Ingredient(RICE_NOODLES, 180),
            Ingredient(STOCK, 330),
            Ingredient(SHRIMP, 25),
            Ingredient(PORK_BELLY, 25, "raw weight"),
            Ingredient(EGGPLANT, 40),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 12, "standing in for mắm cá linh"),
        ],
        ["bun mam"],
        note="Asserted 100.",
    ),
    Recipe(
        "Cháo lòng",
        "Offal rice porridge",
        [
            Ingredient(RICE_DRY, 45, "cooked down in the recipe, not before it"),
            Ingredient(WATER, 280, "a porridge is mostly this"),
            Ingredient(CHITTERLINGS, 40),
            Ingredient(PORK_LIVER, 30),
            Ingredient(SCALLION, 10),
            Ingredient(FISH_SAUCE, 5),
        ],
        ["chao long", "cháo"],
        note="Rule 2 from the module docstring again: the rice is cooked inside "
        "the recipe, because a porridge's water is the dish. Comes out near 75 "
        "against an asserted 90 — the asserted figure looks like a bowl of "
        "congee thicker than the one most shops serve.",
    ),
    Recipe(
        "Lẩu",
        "Hotpot",
        [
            Ingredient(STOCK, 400),
            Ingredient(BEEF_ROUND, 40),
            Ingredient(SHRIMP, 40),
            Ingredient(TOFU, 40),
            Ingredient(MUSHROOM, 40),
            Ingredient(LETTUCE, 50, "standing in for the leafy greens"),
            Ingredient(RICE_NOODLES, 60),
            Ingredient(FISH_SAUCE, 8),
        ],
        ["lau", "lẩu thái", "lẩu bò"],
        note="**A category, not a dish**, and the widest one in this file: what "
        "is in the pot varies more than any recipe here can express, and a "
        "diner eats a share of it rather than a serving. This is a mixed pot at "
        "one person's share, which is the most honest thing a single row can "
        "be — and it is the row most worth correcting by hand. Asserted 80.",
    ),
    # ---- Sticky rice cakes. Dense, and the two differ only in shape and a
    # little pork, so they are written as the same cake twice rather than one
    # aliased to the other — a reader comparing them should see both.
    Recipe(
        "Bánh chưng",
        "Square sticky rice cake",
        [
            Ingredient(GLUTINOUS_RICE_DRY, 100),
            Ingredient(WATER, 90, "taken up steaming"),
            Ingredient(MUNG_BEANS, 45),
            Ingredient(PORK_BELLY, 35, "raw weight; renders into the rice"),
        ],
        ["banh chung"],
        note="Asserted 220.",
    ),
    Recipe(
        "Bánh tét",
        "Cylindrical sticky rice cake",
        [
            Ingredient(GLUTINOUS_RICE_DRY, 100),
            Ingredient(WATER, 95),
            Ingredient(MUNG_BEANS, 45),
            Ingredient(PORK_BELLY, 30, "raw weight"),
        ],
        ["banh tet"],
        note="Asserted 210.",
    ),
    Recipe(
        "Bánh giò",
        "Pyramid rice dumpling",
        [
            Ingredient(RICE_FLOUR, 55),
            Ingredient(TAPIOCA, 10, "for the soft, translucent dough"),
            Ingredient(WATER, 90),
            Ingredient(PORK_GROUND, 35),
            Ingredient(MUSHROOM, 20, "wood ear, standing in"),
            Ingredient(OIL, 3),
            Ingredient(SCALLION, 5),
        ],
        ["banh gio"],
        note="Asserted 160.",
    ),
    # ---- Sweets and drinks. The reference table's last holdings, and the place
    # where "per 100 g of the dish as served" needs saying out loud: a drink is
    # weighed as the liquid, never with its ice.
    Recipe(
        "Bánh flan",
        "Crème caramel",
        [
            Ingredient(EGG_RAW, 55, "one egg"),
            Ingredient(WHOLE_MILK, 90),
            Ingredient(CONDENSED_MILK, 35),
            Ingredient(SUGAR, 12, "the caramel"),
        ],
        ["banh flan", "kem flan", "caramen"],
        note="Asserted 145.",
    ),
    Recipe(
        "Chè",
        "Sweet dessert soup",
        [
            Ingredient(MUNG_BEANS, 60),
            Ingredient(TAPIOCA, 15),
            Ingredient(SUGAR, 20),
            Ingredient(COCONUT_MILK, 30),
            Ingredient(WATER, 120),
        ],
        ["che", "chè đậu xanh", "chè thập cẩm"],
        note="**A category**, like lẩu: chè names a hundred desserts sharing "
        "only sugar and a liquid. Written as a mung bean chè with coconut milk, "
        "the most common shape. Comes out near 105 against an asserted 150, and "
        "the gap is real rather than an error — a chè with more syrup or "
        "condensed milk is heavier than this one.",
    ),
    Recipe(
        "Sữa chua",
        "Vietnamese yoghurt",
        [
            Ingredient(YOGURT, 90),
            Ingredient(CONDENSED_MILK, 12),
        ],
        ["sua chua", "da ua", "yaourt"],
        note="Set with condensed milk rather than merely sweetened with it, "
        "which is what makes Vietnamese yoghurt denser than the plain row it is "
        "built from. Asserted 80.",
    ),
    Recipe(
        "Nước mía",
        "Sugarcane juice",
        [
            Ingredient(CANE_SYRUP, 21),
            Ingredient(WATER, 79, "juice is dilute syrup, not the other way round"),
            Ingredient(LIME_JUICE, 3, "the kumquat it is pressed with"),
        ],
        ["nuoc mia"],
        note="USDA has no sugarcane juice, only cane syrup — which is the same "
        "plant with the water boiled off. Diluting it back to about 15 g of "
        "sugar per 100 g puts it at cane juice's usual 14–18 °Brix. That "
        "dilution is the editorial judgement here; the sugar itself is measured. "
        "Asserted 60.",
    ),
    Recipe(
        "Sữa đậu nành",
        "Soy milk",
        [
            Ingredient(SOYMILK, 200),
            Ingredient(SUGAR, 10),
        ],
        ["sua dau nanh"],
        note="Built from the *unsweetened* row plus the sugar a Vietnamese "
        "street glass actually carries, rather than from a pre-sweetened row "
        "whose sugar is somebody else's. Asserted 45.",
    ),
    Recipe(
        "Cà phê sữa đá",
        "Iced coffee with condensed milk",
        [
            Ingredient(COFFEE, 70, "phin-brewed, so strong and short"),
            Ingredient(CONDENSED_MILK, 28),
        ],
        ["ca phe sua da", "cà phê sữa", "bạc xỉu"],
        note="**The ice is deliberately not in the serving.** It melts into the "
        "same glass, so counting it would make the drink look weaker the longer "
        "it sits, and the density would depend on when it was weighed. The user "
        "is asked for grams of the drink. Comes out near 90 against an asserted "
        "80, which is what the ice was quietly doing to that figure.",
    ),
    # ---- Whole foods, which are one USDA row each rather than a derivation.
    #
    # A one-ingredient recipe looks like a joke until you read what it is for.
    # These rows were **already** USDA's numbers — the asserted table gave banana
    # 89, apple 52, orange 47, mango 60, papaya 43, guava 68, every one of them
    # SR Legacy's figure to the decimal. Whoever wrote the table read them off
    # USDA and did not say so, which is the whole problem in miniature: the
    # nutrition was never the doubtful part, the *provenance* was. Converting
    # them moves not one calorie and gives every one of them an `fdcId`.
    #
    # So the mechanism is not being abused. `Ingredient(BANANA, 100)` states
    # exactly the claim being made — this dish is this row — and states it in the
    # one place a reader already looks.
    Recipe("Táo", "Apple", [Ingredient(APPLE, 100)]),
    Recipe("Chuối", "Banana", [Ingredient(BANANA, 100)]),
    Recipe("Cam", "Orange", [Ingredient(ORANGE, 100)]),
    Recipe("Xoài", "Mango", [Ingredient(MANGO, 100)]),
    Recipe("Dưa hấu", "Watermelon", [Ingredient(WATERMELON, 100)]),
    Recipe("Đu đủ", "Papaya", [Ingredient(PAPAYA, 100)]),
    Recipe("Ổi", "Guava", [Ingredient(GUAVA, 100)]),
    Recipe("Dưa leo", "Cucumber", [Ingredient(CUCUMBER, 100)], ["dưa chuột"]),
    Recipe("Trứng luộc", "Boiled egg", [Ingredient(EGG_BOILED, 100)]),
    # `Thanh long` stays asserted on purpose: SR Legacy has no dragon fruit and
    # no pitaya, so there is nothing to cite. Deleting the row instead would send
    # the dish to the unresolved branch and make the user type figures the table
    # already has — worse for them, and no more honest, since `is_reference`
    # already says exactly what that number is.
    #
    # ---- Three plates that are dishes rather than rows.
    Recipe(
        "Canh rau",
        "Vegetable soup",
        [
            Ingredient(STOCK, 220),
            Ingredient(PAK_CHOI, 60, "standing in for the greens of the day"),
            Ingredient(SCALLION, 5),
            Ingredient(FISH_SAUCE, 5),
        ],
        ["canh"],
        note="The thin soup that comes with a rice meal, not a course. Asserted 30.",
    ),
    Recipe(
        "Cá nướng",
        "Grilled fish",
        [
            Ingredient(TILAPIA, 120),
            Ingredient(OIL, 4, "brushed on before grilling"),
            Ingredient(FISH_SAUCE, 5),
        ],
        ["ca nuong"],
        note="Asserted 160.",
    ),
    Recipe(
        "Salad trộn",
        "Mixed salad",
        [
            Ingredient(LETTUCE, 60),
            Ingredient(CUCUMBER, 40),
            Ingredient(TOMATO, 40),
            Ingredient(CARROT, 25),
            Ingredient(OIL, 6),
            Ingredient(LIME_JUICE, 6),
            Ingredient(SUGAR, 3),
        ],
        ["salad"],
        note="`gỏi` was an alias of this row in the asserted table and is not "
        "one here: gỏi has its own recipe, with shrimp and peanuts, and is a "
        "different dish from a bowl of dressed leaves. Asserted 60.",
    ),
]
