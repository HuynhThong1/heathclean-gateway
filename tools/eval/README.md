# Nutrition resolution coverage

`plan.md` §29 asks for four measures of the pipeline. Three need photographs.
This one needs only a list of dish names, so it can be run today — and it is the
one that says whether the nutrition half of the gateway is doing its job.

```bash
NUTRITION_SOURCES=local .venv/bin/python -m tools.eval.resolve_coverage
.venv/bin/python -m tools.eval.resolve_coverage --sources openfoodfacts,local \
    --corpus global_dishes --limit 20 --concurrency 1
```

## The corpora, and why they are name lists

`corpus/vietnamese_dishes.txt` — 153 dishes from Wikipedia's *List of Vietnamese
dishes* (CC BY-SA 4.0). **Deliberately not derived from
`app/nutrition/vietnamese_foods.py`**: a table measured against its own contents
scores 100% and means nothing.

`corpus/global_dishes.txt` — the 150 most frequent labels in
[MM-Food-100K](https://huggingface.co/datasets/Codatta/MM-Food-100K)
(OpenRAIL-M, non-commercial), which is what the app meets outside Vietnamese
food: Western dishes, fruit, packaged items.

Both are **names only**. In a food dataset the licensed asset is the
photographs; a list of dish names carries none of that, which keeps every
dataset licence out of this repository while still giving the measurement
something honest to run against.

## What it measured, 2026-08-14

| Corpus | `local` only | with `openfoodfacts` |
| --- | --- | --- |
| Vietnamese (153) | **25%** (39) | not run — see below |
| Global (150) | 10% (15) | **70%** on the first 20 |

Three things follow.

**The 88-row table covers a quarter of a real Vietnamese menu.** Not a
projection — 39 of 153 names it did not write itself. The misses are printed as
a worklist, and they are not exotic: bún chả, bún thang, cao lầu, bánh bột lọc,
bánh tráng, cơm hến, xôi gà.

**Open Food Facts is worth turning on, and it is free** — it needs only an
identifying `OPENFOODFACTS_USER_AGENT`, no key. It took the global corpus from
10% to 70% on the sample.

**But coverage is not correctness, and Open Food Facts is a *packaged product*
database.** An exact name match returns one specific barcode's figures, not a
generic average for the dish:

| Query | Matched | kcal/100 g |
| --- | --- | --- |
| Watermelon | a product named "Watermelon" | 31 — right |
| Pizza | a product named "Pizza" | 261 — plausible |
| Fried Rice | a product named "Fried Rice" | 197 — plausible |
| **Fried Chicken** | a product named "Fried Chicken" | **536** — roughly double a real portion of fried chicken |
| Apple | — | miss; a raw fruit is not a packaged product |

So adding `openfoodfacts` buys breadth on packaged and branded food and should
not be read as buying accuracy on cooked dishes. That is a reason to keep USDA
ahead of it in `NUTRITION_SOURCES`, which the default ordering already does.

**And it cannot help Vietnamese food.** Phở and bún chả are cooked dishes, not
barcoded products; the chain has no source that knows them. Vietnamese coverage
moves only when a Vietnamese nutrition dataset replaces the reference table —
the licensed dataset `plan.md` §10 already requires before release.

## Rerunning it

The numbers above are a snapshot, not a fixture. `local` is deterministic and
cheap. Open Food Facts rate-limits *search* to roughly ten requests a minute, so
use `--limit` and `--concurrency 1` against it; a full corpus run is both slow
and rude. USDA needs `USDA_API_KEY` and has not been measured here at all.
