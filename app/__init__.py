"""Loads `.env` before anything else in the package imports.

This has to happen here rather than in `main`. `registry` instantiates every
provider at import time, and each provider reads its configuration in
`__init__` — so by the time `app.main` runs its own imports, the environment is
already too late to change. `app/__init__.py` is imported first by definition.

`.gitignore` already excluded `.env`, but nothing read it, so a `.env` file sat
there doing nothing and the key had to be exported by hand.
"""

from dotenv import load_dotenv

# override=False: a variable already exported wins over the file, so a one-off
# `GEMINI_MODEL=… uvicorn …` still does what it looks like it does.
load_dotenv(override=False)
