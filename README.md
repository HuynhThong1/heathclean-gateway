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
                                          nutrition resolver
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
load. That one is transient: retry.

The nutrition table in `app/nutrition/vietnamese_foods.py` holds approximate
reference values so the pipeline is exercisable — it is **not** a sourced
database. `plan.md` Phase 3 replaces it with USDA and Open Food Facts. Do not
ship it to real users as fact.

## Privacy

The image is held in memory for the request and never written to disk; nothing
about the user is stored here at all (`plan.md` §20, §21). Note that hosted
providers do receive the photo — that is the trade the plan accepts for
recognition, and it is why on-device inference is Phase 8.
