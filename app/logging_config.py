"""Readable gateway logs: a timestamp in local time, and colour by severity.

Uvicorn's defaults give neither. Its access line is
`INFO:     127.0.0.1:56318 - "GET /healthz HTTP/1.1" 200 OK` — no date, no
time, so a log read after the fact cannot answer *when*, which is the first
question anyone asks of one.

Three things this sets up, each for a reason worth keeping:

1. **Local time with the offset written out.** The container runs on UTC and the
   people reading these logs are on UTC+7, so a bare timestamp is off by seven
   hours in the direction nobody notices — it looks like a plausible time.
   Printing `+07` beside it is what stops that mistake recurring.
2. **Colour, chosen deliberately rather than auto-detected.** See `use_colors`.
3. **The healthcheck is filtered out of the access log.** See `HealthCheckFilter`.
"""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from logging.config import dictConfig

import click
import uvicorn.logging

#: The container healthcheck's path. Not `/v1`-prefixed and not authenticated,
#: so it is also the one route a reverse proxy or uptime monitor will hit.
HEALTH_PATH = "/healthz"


def log_timezone() -> timezone:
    """The zone timestamps are printed in. UTC+7 unless told otherwise.

    A **fixed offset**, not `ZoneInfo("Asia/Ho_Chi_Minh")`. Vietnam has observed
    UTC+7 with no daylight saving since 1975, so the two are identical here —
    and a fixed offset needs no tz database, which a `python:*-slim` image is not
    guaranteed to carry. Somewhere that does observe DST should set
    `LOG_UTC_OFFSET_HOURS` and accept that it will not shift itself, or swap
    this for `ZoneInfo` and add `tzdata` to requirements.
    """
    try:
        hours = float(os.getenv("LOG_UTC_OFFSET_HOURS", "7"))
    except ValueError:
        hours = 7.0
    return timezone(timedelta(hours=hours))


def use_colors() -> bool:
    """Whether to emit ANSI escapes.

    **`auto` is the default and it says no inside a container**, which is the
    whole reason this is configurable. A container's stdout is a pipe, not a
    terminal, so `isatty()` is False even when the person reading
    `docker compose logs -f` is sitting at one — auto-detection would correctly
    answer a question nobody asked. `docker-compose.yml` therefore sets
    `LOG_COLORS=1` explicitly.

    `0` turns them off for a file, a log shipper or anything that stores the
    bytes: ANSI escapes in a stored log are worse than no colour at all.
    `NO_COLOR` is honoured because it is the cross-tool convention
    (https://no-color.org) and costs one line.
    """
    setting = os.getenv("LOG_COLORS", "auto").strip().lower()
    if os.getenv("NO_COLOR"):
        return False
    if setting in {"1", "true", "yes", "always"}:
        return True
    if setting in {"0", "false", "no", "never"}:
        return False
    return sys.stderr.isatty()


class _LocalTimeMixin:
    """Stamps every record in `log_timezone()` and dims it.

    `logging.Formatter` has a `converter` hook, but it deals in `time.struct_tm`
    and so cannot carry an offset — the offset is exactly what has to be visible
    here. Overriding `formatTime` is the version that can print `+07`.
    """

    def formatTime(self, record, datefmt=None):  # noqa: N802 - logging's spelling
        stamp = datetime.fromtimestamp(record.created, log_timezone())
        text = stamp.strftime(datefmt or "%Y-%m-%d %H:%M:%S %z")
        # Grey: the timestamp is on every line, so it is the thing that should
        # recede when someone is scanning for the one line that matters.
        return click.style(text, fg="bright_black") if self.use_colors else text


class DefaultFormatter(_LocalTimeMixin, uvicorn.logging.DefaultFormatter):
    """Startup, shutdown and anything the app logs itself."""


class AccessFormatter(_LocalTimeMixin, uvicorn.logging.AccessFormatter):
    """One line per request.

    Uvicorn's own class already colours the status code by class — green for
    2xx, yellow for 4xx, red for 5xx — which is most of what makes an access log
    skimmable. Only the timestamp is added.
    """


class HealthCheckFilter(logging.Filter):
    """Drops the container healthcheck's successful requests.

    It runs every 30 seconds, so it writes about 2.900 lines a day, and the
    screenshot that prompted this was *entirely* `GET /healthz 200 OK` — real
    traffic was not hard to read so much as impossible to find. Nothing is
    learned from the 2.900th one.

    **A failing healthcheck still logs**, because that is a fact about the
    service rather than noise; only 2xx is dropped. `LOG_HEALTHZ=1` brings the
    successful ones back for anyone debugging the probe itself.
    """

    def __init__(self) -> None:
        super().__init__()
        self.enabled = os.getenv("LOG_HEALTHZ", "").strip().lower() not in {
            "1",
            "true",
            "yes",
        }

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.enabled:
            return True
        # uvicorn.access passes (client_addr, method, path, http_version, status).
        args = record.args
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        path, status = args[2], args[4]
        try:
            is_ok = 200 <= int(status) < 300
        except (TypeError, ValueError):
            return True
        return not (path == HEALTH_PATH and is_ok)


def logging_config() -> dict:
    colors = use_colors()
    return {
        "version": 1,
        # The app's own loggers are created at import time, before this runs.
        # Disabling them here would silence exactly the code that has something
        # to say.
        "disable_existing_loggers": False,
        "filters": {"healthcheck": {"()": HealthCheckFilter}},
        "formatters": {
            "default": {
                "()": DefaultFormatter,
                "fmt": "%(asctime)s %(levelprefix)s %(message)s",
                "use_colors": colors,
            },
            "access": {
                "()": AccessFormatter,
                "fmt": '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                "use_colors": colors,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["healthcheck"],
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
            # Anything under `app.*`, so the gateway's own messages get the same
            # timestamp and colour as uvicorn's rather than the root logger's
            # bare format.
            "app": {"handlers": ["default"], "level": os.getenv("LOG_LEVEL", "INFO"), "propagate": False},
        },
    }


def configure_logging() -> None:
    """Applied at import of `app.main`, which is late enough to win.

    Uvicorn configures logging while building its `Config`, and only then
    imports the application — so a `dictConfig` run at app-import time replaces
    what uvicorn just installed. Doing it here rather than through
    `--log-config` means every way of starting the service gets it: the
    container's `python -m uvicorn`, a bare `uvicorn` on a VPS, `fastapi dev`,
    and the test suite.
    """
    dictConfig(logging_config())
