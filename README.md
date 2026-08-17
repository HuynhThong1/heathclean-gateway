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
                       (recipe / USDA / OFF / reference)
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

### Logs

Every line is stamped in **UTC+7 with the offset printed**, and coloured by
severity — `app/logging_config.py`. Uvicorn's own format has no timestamp at
all, which leaves a log unable to answer the first question anyone asks of one;
and the container clock runs on UTC, so a bare time would be seven hours out in
the direction that still looks plausible.

```
2026-08-17 11:34:47 +0700 INFO:     10.0.0.4:41124 - "POST /v1/meals/analyze HTTP/1.1" 200 OK
2026-08-17 11:34:47 +0700 INFO:     10.0.0.4:41125 - "POST /v1/meals/analyze HTTP/1.1" 401 Unauthorized
```

| Variable | Default | |
| --- | --- | --- |
| `LOG_UTC_OFFSET_HOURS` | `7` | A fixed offset, not a tz name — Vietnam has had no DST since 1975, and a slim image may carry no tz database. |
| `LOG_COLORS` | `auto` | `auto` means "is stderr a terminal", which inside a container is always **no**. `docker-compose.yml` sets `1`. `NO_COLOR` overrides everything. |
| `LOG_HEALTHZ` | unset | The healthcheck's **successful** requests are dropped: every 30s is ~2.900 lines a day, and they bury real traffic. A *failing* healthcheck always logs. Set `1` to see them all. |
| `LOG_LEVEL` | `INFO` | For the gateway's own `app.*` loggers. |

Piping to a file or a log shipper? Set `LOG_COLORS=0`, or the stored bytes carry
ANSI escapes.

Copy `.env.example` as a starting point. Nutrition sources are opt-in and
ordered; the first exact name match wins:

```bash
NUTRITION_SOURCES=derived,usda,openfoodfacts,reference
USDA_API_KEY=…
OPENFOODFACTS_USER_AGENT=HeathFirst/0.1 (team@example.com)
```

The default is only `local`, so tests and a fresh clone never make hidden
network calls. USDA requires a [FoodData Central API key](https://fdc.nal.usda.gov/api-guide/).
Open Food Facts requires an identifying User-Agent and is subject to its
[API terms, rate limits and database licence](https://openfoodfacts.github.io/openfoodfacts-server/api/).
Both adapters accept only an exact normalized name match; a merely similar
search result stays unresolved for the user to correct.

**How much any of that resolves is measurable** — `plan.md` §29's
nutrition-resolution rate needs no photographs, only dish names. See
[`tools/eval`](tools/eval/README.md). Against 153 Vietnamese dish names it did
not write, `local` answers **29%**, and two thirds of those answers are now
derived and cited rather than asserted. Adding Open Food Facts takes a global
corpus from 10% to 67% — while returning one branded product's figures rather
than the dish's, which is why it sits behind USDA — and behind `derived`.

**The order is load-bearing.** With Open Food Facts ahead of the local tables, a
deployed gateway resolved a 400 g bowl of phở to a packet of Shan Noodle instant
soup — a real product named "Beef Pho" at 367 kcal/100 g — and reported **1,467
kcal** instead of 268. `derived` and `reference` are separate sources so a recipe
can be asked first and an asserted row last.

### Where a Vietnamese dish's numbers come from

`local` is two tables. [`recipes.py`](app/nutrition/recipes.py) writes a dish as
a serving in grams over USDA FoodData Central rows (CC0 public domain), and
`derived_foods.py` is generated from it — so a figure can be checked against
`https://fdc.nal.usda.gov/food-details/<fdcId>/nutrients` instead of taken on
trust. `vietnamese_foods.py` is the older hand-written table and still answers
for dishes no recipe covers yet; those responses keep `nutritionIsReference=true`.

This exists because there is nothing to buy. The **Vietnamese Food Composition
Table** (Ministry of Health, 2017) is a printed book with no download and no
stated licence, and USDA — CC0 and bulk-downloadable without a key — contains no
Vietnamese dishes at all. National tables list *ingredients*; a restaurant dish
is not an ingredient, so "Bún chả" has to be derived rather than licensed. The
nutrition is measured and public-domain; what stays editorial is the **portions**,
and that is what a reader should argue with.

    python tools/nutrition/generate_derived.py <SR Legacy json> --write

```bash
curl -X POST http://127.0.0.1:8000/v1/meals/analyze \
  -F "image=@meal.jpg;type=image/jpeg"
```

Tests: `.venv/bin/python -m pytest tests -q`

## Deploying to a VPS

The service is stateless — no database, no disk writes, no session — so a
deployment is one container and nothing else.

### Push an image, or build on the VPS

Both work. What must not be skipped either way is the architecture.

**`--platform linux/amd64` is mandatory when building on a Mac.** Apple silicon
produces `linux/arm64` by default, a VPS is almost always `amd64`, and the
mismatch is not caught at build time — the container starts and dies with
`exec format error`.

```bash
# On the Mac: build for the target and push
docker buildx build --platform linux/amd64 \
  -t ttl.sh/healthclean-gateway:24h --push .
```

```bash
# On the VPS: no source tree needed, only this file and .env
cp .env.example .env
openssl rand -hex 32          # paste into GATEWAY_API_KEY
$EDITOR .env                  # MODEL_PROVIDER, GEMINI_API_KEY, GATEWAY_API_KEY
docker compose pull
docker compose up -d
curl -s localhost:8000/healthz
```

`ttl.sh` is an **ephemeral, anonymous, public** registry: no login, the tag is
the lifetime, and 24h is its maximum. That makes it a good way to move a build
onto a box once and a bad thing for a deployment to depend on — the image is
gone tomorrow, so a host that has pruned it cannot pull again. Anyone who
guesses the name can pull it too, which is tolerable only because `.env` is
excluded and the image carries no credentials. For anything lasting, use a real
registry (GHCR, a private one) or build on the VPS:

```bash
git clone <this repo> healthclean-gateway && cd healthclean-gateway
docker compose up -d --build     # no architecture question at all
```

Docker Hub rate-limits anonymous pulls hard enough to fail a first build, which
is why the base image here is pulled through `public.ecr.aws`'s mirror of the
official images rather than from Docker Hub directly.

### The API key is not optional here

Every `/v1` route requires `X-API-Key` once `GATEWAY_API_KEY` is set, and
`docker-compose.yml` refuses to start without it. An unset key leaves the
gateway open, which is right on localhost and wrong on a public port: one
`POST /v1/meals/analyze` spends a call on the operator's Gemini key, and the
free tier's daily quota is small enough to exhaust in an afternoon. `/healthz`
stays unauthenticated for the container healthcheck.

```bash
curl -X POST http://<vps>:8000/v1/meals/analyze \
  -H "X-API-Key: $GATEWAY_API_KEY" \
  -F "image=@meal.jpg;type=image/jpeg"
```

The key is **mounted, never baked in** — `.dockerignore` excludes `.env`, and
compose mounts it read-only at `/srv/.env`. Anyone who can pull an image can
read its layers, so a key copied in at build time is a key published.

That mount is why **`chmod 600 .env` on the VPS is the wrong instinct.** The
container runs as uid 10001, a Linux bind mount passes the host's ownership
straight through, and a secrets-tight file owned by the deploy user is then
unreadable to the process that needs it. It does not fail loudly: compose
passes `GATEWAY_API_KEY` through `environment:` from its own reading of `.env`
on the host, so authentication still works and the gateway looks fine — while
`GEMINI_API_KEY`, which is only ever read from inside, never loads and every
analysis fails as a provider error. Check `GET /v1/providers` reports
`"configured": true` after a deploy. Keep the file readable (`644`) and rely on
the directory for privacy, or `chown 10001` it. (Docker Desktop on macOS hides
this: its VM shares files without preserving host uid, so a local
`docker compose` run reads a `600` file happily and a Linux host will not.)

Changing `.env` still needs a restart, for the reason in "Running it" above —
providers read their configuration at import. Containerised that is
`docker compose restart`. `GATEWAY_API_KEY` is the exception: it is read per
request, so rotating it takes effect on the mount without one.

### Plain HTTP is a stopgap

An iOS client cannot reach `http://<ip>:8000` without an App Transport Security
exception naming that exact address, and the key then crosses the network in
clear text. That is acceptable while testing against an IP and not acceptable
in the client's hands.

The fix is a domain, not more configuration. With one pointed at the VPS, put
Caddy in front — it obtains and renews a certificate unprompted, the compose
service stops publishing 8000 to the world, and the iOS side drops its ATS
exception entirely.

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

The third one could **not** be fixed in the prompt, and it is the interesting
case. A bowl of bún thịt nướng with spring rolls came back as `Bún thịt nướng
chả giò` — one item, 95% confidence, 0 kcal. The table had `Bún thịt nướng` and
`Chả giò` as separate rows and nothing for the combination, so it missed. The
same photo had resolved a few days earlier, because that call the model had
named it `Bún thịt nướng`: **the model's naming is not stable between calls, and
exact matching turns that into a coin flip.**

The model was not wrong either — a Vietnamese menu really does list that as one
line, which is precisely what the prompt asks for. The mismatch is between how
menus name combinations and how the table is keyed, so the fix was a **row of
its own** (`recipes.py`), not an alias: aliasing the compound name onto the
plain bowl would have priced 450 g at 129 kcal/100 g instead of 161 and lost the
rolls at 319 — 580 kcal against 724, a silent 20% under-count. Under-counting is
the one thing the unresolved state exists to prevent, so a combination dish that
is not in the table must keep missing until someone writes it a recipe.

So a scan can come back 0 kcal with nothing whatsoever wrong in the code. If
that happens, suspect the granularity of the names before anything else — and
if the name looks *right*, check whether it is a combination the table has only
the halves of.

### A wrong number is worse than no number

The failures above all end at 0 kcal, which is visible. This one did not.

A bowl of **mì cay** came back at **3.000 kcal**. The model named it in English —
`Spicy Noodle Soup` — which exactly matched a *packaged product* of that name in
Open Food Facts, barcode `0193937000288`, at 461 kcal/100 g. That is the density
of the **dry packet**. The 650 g the model estimated is the **cooked bowl**, most
of which is broth. Multiply one by the other and the client is shown a figure
four times too large with nothing to suggest it is wrong.

The mismatch is of **units, not of names**: a barcode's per-100 g is "as sold",
and a dish needs "as served". Nothing in the data says which products are sold
dry, so three things now stand between that and the client:

1. **A ceiling on a single item** (`resolver.IMPLAUSIBLE_ITEM_CALORIES`, 1.200
   kcal). Over it, the item falls back to *unresolved* and the user types the
   figure. Grounded in this project's own table: the heaviest serving it derives
   is Cơm sườn at 699 kcal. The check is on the **total, not the density** —
   a 100 g bag of crisps at 530 kcal/100 g is correct, and packaged food is the
   one thing Open Food Facts is actually for.
2. **A startup warning** when `NUTRITION_SOURCES` puts a network source ahead of
   the recipes. This had already happened once — a bowl of phở against a
   packaged "Beef Pho" at 367 kcal/100 g, reported as 1.467 kcal — and
   `.env.example` was fixed then. **The deployed `.env` never was.** A comment in
   a file nobody reruns did not prevent the second incident; a warning against
   the configuration actually in force might.
3. **A recipe for Mì cay**, so the dish resolves on its own name rather than
   falling through to a barcode at all.

The prompt now also insists that `name` carries the Vietnamese name, since it
was an English one that reached Open Food Facts in the first place.

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
