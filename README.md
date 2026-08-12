# HealthClean AI gateway

Recognizes foods in a meal photo and resolves their nutrition. The iOS client
([`heathclean`](https://github.com/HuynhThong1/heathclean)) talks to this over
the contract in that repo's `plan.md` §25.

## The rule this service exists to enforce

**The model never decides calories.** A provider identifies foods and estimates
portions; the nutrition resolver turns grams into energy. That split is
`plan.md` §2, and it is why swapping models cannot change the numbers a user
sees — only which foods get named.

```
photo ──> provider (Qwen / Gemini / mock) ──> [{name, grams, confidence}]
                                                      │
                              ordered nutrition sources
                                  (USDA / OFF / local)
                                                      │
                                    [{name, grams, kcal, p/c/f}] + total
```

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Configuration comes from a `.env` file in the repo root (gitignored), loaded by
`app/__init__.py` — it has to happen there rather than in `main`, because
`registry` builds every provider at import time and each one reads its
configuration in `__init__`. An already-exported variable still wins, so a
one-off `GEMINI_MODEL=… uvicorn …` does what it looks like it does.

```bash
MODEL_PROVIDER=gemini
GEMINI_API_KEY=…
GEMINI_MODEL=gemini-3.6-flash
```

Changing `.env` needs a **restart**: `--reload` watches code, not the
environment, and providers have already read it by then.

Copy `.env.example` as a starting point. Nutrition sources are opt-in and
ordered; the first exact name match wins:

```bash
NUTRITION_SOURCES=usda,openfoodfacts,local
USDA_API_KEY=…
OPENFOODFACTS_USER_AGENT=HeathFirst/0.1 (team@example.com)
```

The default is only `local`, so tests and a fresh clone never make hidden
network calls. USDA requires a [FoodData Central API key](https://fdc.nal.usda.gov/api-guide/).
Open Food Facts requires an identifying User-Agent and is subject to its
[API terms, rate limits and database licence](https://openfoodfacts.github.io/openfoodfacts-server/api/).
Both adapters accept only an exact normalized name match; a merely similar
search result stays unresolved for the user to correct.

```bash
curl -X POST http://127.0.0.1:8000/v1/meals/analyze \
  -F "image=@meal.jpg;type=image/jpeg"
```

Tests: `.venv/bin/python -m pytest tests -q`

## Switching models

Switching is configuration, never a code change.

```bash
MODEL_PROVIDER=qwen QWEN_BASE_URL=http://localhost:11434/v1 \
  .venv/bin/python -m uvicorn app.main:app
```

Or per request, which is what makes comparing two models on the same photo
practical:

```bash
curl -X POST http://127.0.0.1:8000/v1/meals/analyze \
  -H "X-Model-Provider: gemini" -F "image=@meal.jpg;type=image/jpeg"
```

`GET /v1/providers` lists what is registered and which are usable right now, so
a client can avoid offering a provider that has no key.

`GET /v1/nutrition/sources` reports lookup order and configuration. Every
resolved item also returns `nutritionSource`, `nutritionSourceId`,
`nutritionSourceURL`, and `nutritionIsReference`, so the client can retain and
show where its numbers came from.

| Provider | Env | Notes |
| --- | --- | --- |
| `mock` | — | Deterministic on the image bytes. Development and tests. |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` | `plan.md` §31's POC choice. |
| `qwen` | `QWEN_BASE_URL`, `QWEN_API_KEY`, `QWEN_MODEL` | OpenAI-shaped, so DashScope, OpenRouter, vLLM and Ollama all work. |

### Adding a provider

Subclass `FoodRecognitionProvider`, return `RecognizedFood`s, register it in
`app/providers/registry.py`. Reuse `RECOGNITION_PROMPT` — if each provider
carried its own prompt, comparing two models would also be comparing two
prompts.

## What is verified, and what is not

`mock` is exercised end to end by the test suite and by hand over HTTP.

**`gemini` is verified against the live API.** A photo of phở resolved to
`Phở bò`, 650 g, 585 kcal at confidence 0.95 — recognition, parsing and the
nutrition lookup, all the way through.

Getting there took two fixes, and both were to the *prompt* rather than the code:

1. The model first returned the **ingredients** — bánh phở, thịt bò, nước dùng,
   hành lá — and not one of them resolved. `vietnamese_foods` is keyed on whole
   dishes, so asking for "every visible food item" guarantees zero calories on a
   dish that is sitting in the table.
2. Naming at menu level then gave `Phở bò tái chín`, which still missed:
   `lookup` is exact-match by design and menu names carry preparation variants.
   The prompt now asks for the base dish name.

So a scan can come back 0 kcal with nothing whatsoever wrong in the code. If
that happens, suspect the granularity of the names before anything else.

**`qwen` has never been run.** No endpoint was available, so its request shape
follows the published OpenAI-compatible contract but is unproven.

Model names rot. `gemini-2.0-flash` — the old default here — and the entire
`gemini-2.5-*` line now return 404 "no longer available to new users", which is
why the default is the `gemini-flash-latest` alias; pin a version in `.env` when
a comparison has to be reproducible. A live model can still return **503** under
load. That one is transient: retry. **429** is not: the free tier's daily quota
is per model and small enough to exhaust in an afternoon of testing, and it
resets at midnight Pacific.

`gemini-3.1-flash-lite` is what `.env` pins. On the phở photo it produced results
identical to `gemini-3.6-flash` — same dish, same 650 g, same 585 kcal — and it
has its own quota budget, which is what mattered once 3.6 hit 429. Choosing it on
"which model names dishes more specifically in three words" was the wrong test;
the task is JSON with a base dish name and a gram estimate, and on that they tied.

### Confidence is not calibrated

Three photos through `gemini-3.1-flash-lite`:

| Photo | Result | Confidence | |
| --- | --- | --- | --- |
| Phở | Phở bò · 650 g · 585 kcal | 1.00 | correct |
| Bún bò Huế | **Phở bò** · 650 g · 585 kcal | **0.98** | wrong |
| Bánh mì | Bánh mì thịt · 250 g · 625 kcal | 0.95 | correct |

The miss is a fair one — two beef noodle soups in broth — but it came back at
0.98. The client flags items below 0.75 for checking (`plan.md` §4), so that
mechanism will not catch this class of error at all: a wrong dish arrives looking
certain. The nutrition gap here is ~14% (bún bò Huế is 105 kcal/100 g against
phở bò's 90).

What protects the user is that the dish name is shown prominently and can be
corrected, not the confidence number. Three samples say nothing about calibration
in general — but they are enough to stop treating a high figure as a guarantee.

The nutrition table in `app/nutrition/vietnamese_foods.py` holds approximate
reference values so the pipeline is exercisable — it is **not** a sourced
database. It remains an explicit fallback and responses mark its rows as
`nutritionIsReference: true`. Do not ship those rows to real users as fact;
configure USDA/Open Food Facts first and replace the Vietnamese fallback with
a licensed, cited national dataset when one is selected.

It is 88 rows now rather than 16. On a set of 28 base dish names the old table
resolved 7; this one resolves 28. `_key` also strips Vietnamese accents, so one
row absorbs "Phở bò", "pho bo" and "PHO BO" instead of needing an alias each —
that is normalisation, not fuzzy matching, and `lookup` is still exact. A
preparation variant like "Phở bò tái chín" deliberately still misses.

Two properties the tests hold in place: broth dishes are less calorie-dense than
rice plates (a 650 g bowl and a 250 g plate are not the same food), and every row
is self-consistent under 4/4/9 kcal per gram — that check caught a typo.

## Privacy

The image is held in memory for the request and never written to disk; nothing
about the user is stored here at all (`plan.md` §20, §21). Note that hosted
providers do receive the photo — that is the trade the plan accepts for
recognition, and it is why on-device inference is Phase 8.
