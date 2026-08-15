# Nutrition resolution coverage

`plan.md` §29 asks for four measures of the pipeline. Three need photographs.
This one needs only a list of dish names, so it can be run today — and it is the
one that says whether the nutrition half of the gateway is doing its job.

```bash
.venv/bin/python -m tools.eval.resolve_coverage --sources local
.venv/bin/python -m tools.eval.resolve_coverage --corpus global_dishes \
    --limit 24 --concurrency 1        # network sources: sample, do not sweep
```

It prints which sources actually ran, how many names each answered, how many
answers came from the unsourced reference rows, and every miss — so the output
is a worklist rather than a score.

## The corpora, and why they are name lists

`corpus/vietnamese_dishes.txt` — 153 dishes from Wikipedia's *List of Vietnamese
dishes* (CC BY-SA 4.0). **Deliberately not derived from this repository's own
tables**: a table measured against its own contents scores 100% and means
nothing.

`corpus/global_dishes.txt` — the 150 most frequent labels in
[MM-Food-100K](https://huggingface.co/datasets/Codatta/MM-Food-100K)
(OpenRAIL-M, non-commercial), which is what the app meets outside Vietnamese
food: Western dishes, fruit, packaged items.

Both are **names only**. In a food dataset the licensed asset is the
photographs; a list of dish names carries none of that, which keeps every
dataset licence out of this repository while still giving the measurement
something honest to run against.

## What it measured

| Corpus | before recipes | after the first recipes | now | full chain |
| --- | --- | --- | --- | --- |
| Vietnamese (153) | 25% — 39, all asserted | 29% — 45, of which 30 cited | **29% — all 45 cited** | unchanged |
| Global (150) | 10% — 15 | 10% | 11% — 17, of which **11 asserted** | **67%** on the first 24 |

**Coverage did not move, and that is still not the point.** The Vietnamese
column went from 30 of 45 answers cited to 45 of 45: every dish the offline
chain can name is now computed from a recipe over CC0 USDA rows and carries the
`fdcId`s it was derived from. §10 asks for the *asserted* rows to go, not for
the percentage to climb, and for this corpus they are gone.

The 11 left on the global corpus are the same job in a different shape. They are
mostly whole foods — Apple, Banana, Mango, Boiled Egg — which USDA carries
directly, so each needs a row mapped rather than a dish derived. `Dragon Fruit`
is the one that will not go that way: SR Legacy does not have it.

**A citation is not a portion.** `Lẩu` and `Chè` now cite USDA for every gram in
them and are still the two least trustworthy rows in the file, because each
names a family rather than a dish. What a derived row fixes is where the
nutrition came from; how much of it you were served stays editorial.

**Nothing in the chain can raise the Vietnamese figure.** On the global sample
USDA answered 1 name and Open Food Facts 13; on Vietnamese dishes both answer
essentially nothing, because phở is neither a USDA ingredient nor a barcoded
product. Vietnamese coverage moves only by writing more recipes.

**Open Food Facts is worth having and costs only a User-Agent** — it took the
global corpus from 10% to 67%. But coverage is not correctness, and it is a
database of *packaged products*: an exact name match returns one barcode's
figures, not the dish's.

| Query | Matched | kcal/100 g |
| --- | --- | --- |
| Watermelon | a product named "Watermelon" | 31 — right |
| Pizza | a product named "Pizza" | 261 — plausible |
| Fried Rice | a product named "Fried Rice" | 197 — plausible |
| **Fried Chicken** | a product named "Fried Chicken" | **536** — a snack, not a dish |
| Apple | — | miss; a raw fruit is not a packaged product |

So it buys breadth on branded and packaged food and must stay **behind** USDA in
`NUTRITION_SOURCES`, which the shipped ordering does.

## Why the dishes are derived rather than licensed

There is nothing to buy, and that is not a licensing problem:

- The **Vietnamese Food Composition Table** (Ministry of Health, 2017) is a
  302-page printed book — FAO lists it print-only, no download, no stated
  licence.
- **USDA FoodData Central** is CC0 and bulk-downloadable without an API key, and
  contains **no Vietnamese dishes at all**. SR Legacy's 7,793 rows have rice
  noodles, pork loin, beef round, shrimp and cilantro; nothing called phở, and
  not even fish sauce under that name.

National tables list *ingredients*. A restaurant dish is not an ingredient, so
"Bún chả" cannot be licensed — it has to be derived. That is
[`app/nutrition/recipes.py`](../../app/nutrition/recipes.py): a serving in grams
over public-domain rows, with `derived_foods.py` generated from it. The
nutrition is measured; the **portions** are this project's judgement and are the
part to argue with.

### What the first four dishes settled

| Dish | Derived | Old hand-written row |
| --- | --- | --- |
| Bánh mì thịt | 244 kcal, 13.3 p | 250, 11.0 p |
| Gỏi cuốn | 103 kcal, 10.5 p | 95, 6.0 p |
| Cơm tấm | 140 kcal, **9.4 p** | 150, **3.0 p** |
| Phở bò | 67 kcal | 90 |

Three land within 10 kcal/100 g of the hand-written row, which says those rows
were better than "unsourced" makes them sound. The two disagreements are the
useful part:

- **Cơm tấm's 3.0 g protein was the row's own error.** That is plain rice's
  protein (cơm trắng is 2.7). The dish is a rice plate *with a grilled pork
  chop*, and the app asks the model for grams of the whole plate — so the row
  under-reported protein by about a third of the dish. Cơm gà, right beside it,
  did include its chicken.
- **Phở's gap was the recipe's, twice over.** Modelling broth as plain water put
  it at 47; `Soup, stock, chicken, home-prepared` (36 kcal/100 g) is the closest
  public-domain row to a simmered bone broth and brings it to 67. It stays below
  90 because a 700 g bowl that is more than half broth is not a 90 kcal/100 g
  food — that figure was describing a drained bowl. Broth is the least certain
  number in any of these recipes and it dominates every soup.

## Rerunning it

These are snapshots, not fixtures. `local` is deterministic and costs nothing.
Open Food Facts rate-limits *search* to roughly ten requests a minute, so use
`--limit` and `--concurrency 1` against it — a full corpus sweep is both slow and
rude. USDA needs `USDA_API_KEY`.
