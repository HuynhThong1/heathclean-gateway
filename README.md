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

**`gemini` and `qwen` have never been run.** No API key or endpoint was
available when they were written, so their request shapes follow each vendor's
published contract but are unproven. Treat the first live call as the real test.

The nutrition table in `app/nutrition/vietnamese_foods.py` holds approximate
reference values so the pipeline is exercisable — it is **not** a sourced
database. `plan.md` Phase 3 replaces it with USDA and Open Food Facts. Do not
ship it to real users as fact.

## Privacy

The image is held in memory for the request and never written to disk; nothing
about the user is stored here at all (`plan.md` §20, §21). Note that hosted
providers do receive the photo — that is the trade the plan accepts for
recognition, and it is why on-device inference is Phase 8.
