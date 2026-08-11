"""Pins the provider before the app is imported.

The tests post a handful of fake bytes as the image, which only the mock
provider can answer. They used to get it by accident: nothing read `.env`, so
`MODEL_PROVIDER` was unset and the registry fell back to "mock". Once `.env` was
actually loaded, a developer with `MODEL_PROVIDER=gemini` in it ran the whole
suite against the live API and two tests failed on bytes that are not an image.

A suite whose result depends on the developer's local configuration is not
testing the code, so the provider is set here instead of inherited. This has to
happen before `app` is imported, because `registry` builds every provider at
import time — pytest loads conftest first, which is what makes it work.

`load_dotenv(override=False)` in `app/__init__` then leaves this alone.
"""

import os

os.environ["MODEL_PROVIDER"] = "mock"
