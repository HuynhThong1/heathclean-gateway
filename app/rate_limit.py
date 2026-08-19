"""Two limits, because there are two different failures to prevent.

`GATEWAY_API_KEY` is a single shared secret that ships inside an iOS bundle,
which means it is extractable — authentication decides *whether* a caller may
spend the operator's model quota, and nothing here can stop it leaking. What is
left to decide is *how much*, and that splits in two:

1. **A burst limit, per client, per minute.** Stops one caller — a leaked key,
   a retry loop in the client — from turning the day's budget into a minute's
   traffic. Applied as a route dependency, so a malformed request counts too:
   the thing being rationed at this timescale is the gateway's own attention.
2. **A daily cap on calls to a model, per provider.** The one failure that
   actually hurts is exhausting a hosted provider's daily quota, because 429 is
   not transient — it resets at midnight Pacific and the app is dead until then
   (README, "Model names rot"). The quota is *per model*, so the counter is too.
   This one is consumed in the handler immediately before the provider call, not
   in a dependency: a 415 on a PDF costs no quota and must not spend any.

Neither is a security boundary. State is a dict in this process, so:

* **One worker or the limits multiply.** The Dockerfile runs a single uvicorn
  worker for unrelated reasons (every request awaits a hosted model, which async
  already overlaps), and that is what makes an in-process counter honest. Add
  workers and each gets its own allowance.
* **A restart forgives everything.** Acceptable: `docker compose restart` is an
  operator action, not something an attacker can reach.

Both windows are **rolling**, measured on `time.monotonic`. Rolling is the
conservative choice against a provider that resets at a wall-clock hour — it
never permits more than N in any 24h, where a midnight-reset counter would allow
2N across the boundary — and monotonic time cannot be walked backwards by an NTP
correction the way `time.time` can.

Limits are read per request, like `GATEWAY_API_KEY` and for the same reason: it
is one `getenv` against a network call, and it keeps them settable in a test
without reimporting the app.
"""

import logging
import os
import time
from collections import deque
from typing import Deque, Dict, Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

MINUTE = 60.0
HOUR = 60 * MINUTE
DAY = 24 * HOUR

#: Defaults. The per-minute figure is generous for the real interaction — a few
#: photos while deciding what to log — and still three orders of magnitude below
#: what a script can do. The daily figure is deliberately *not* any provider's
#: published number: it is a guard that has to sit below whatever your key
#: actually has, and free tiers are revised without notice.
DEFAULT_PER_MINUTE = 10
DEFAULT_PER_DAY = 200

#: Above this many tracked clients the table is swept, and if that does not free
#: anything it is dropped entirely. Unbounded memory is a worse failure than a
#: forgiven window, and the burst limiter is not what keeps the quota safe.
MAX_TRACKED_CLIENTS = 4096


def _int_env(name: str, default: int) -> int:
    """A limit from the environment. Unparseable means the default, not a crash:
    a typo in `.env` must not take the service down, and the default is safe."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        logger.warning("%s is not an integer (%r); using %d", name, raw, default)
        return default
    # Negative is meaningless. Zero is documented as "no limit", so it passes
    # through untouched.
    return max(0, value)


def requests_per_minute() -> int:
    return _int_env("RATE_LIMIT_PER_MINUTE", DEFAULT_PER_MINUTE)


def model_calls_per_day() -> int:
    return _int_env("RATE_LIMIT_PER_DAY", DEFAULT_PER_DAY)


def trust_proxy_headers() -> bool:
    """Whether `X-Forwarded-For` may be believed.

    Off by default, because the header is written by whoever sent the request.
    Turning it on is only sound when the gateway is unreachable except through
    the proxy — with Caddy in front that means `GATEWAY_BIND=127.0.0.1`, or the
    per-client limit becomes per-header-value and a caller picks their own.
    """
    return os.getenv("TRUST_PROXY_HEADERS", "").strip().lower() in {"1", "true", "yes"}


def client_identity(request: Request) -> str:
    """What "one client" means for the burst limit.

    The API key cannot serve here — there is exactly one, shared by every
    install, so limiting per key would limit the whole user base as if it were a
    single caller. The address is the only thing left that distinguishes them.
    """
    if trust_proxy_headers():
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # The **last** entry, not the first. A proxy appends the peer it
            # actually spoke to, so the tail is the only hop the client could not
            # choose; the conventional left-most "original client" is precisely
            # the value an attacker writes to get a fresh allowance per request.
            # With the `Caddyfile` in this repo there is only ever one entry —
            # Caddy replaces a caller-supplied header unless the peer is a
            # configured trusted proxy — so this matters the day something else
            # is put in front, which is exactly when nobody re-reads this.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class _RollingWindow:
    """Hit timestamps inside a fixed span, oldest dropped as they age out.

    No lock. Every mutation below runs to completion without an `await`, and
    uvicorn runs one worker on one event loop, so there is no interleaving to
    protect against. That is a property of how this is deployed, not of the
    class — a threaded server would need one.
    """

    __slots__ = ("span", "hits")

    def __init__(self, span: float) -> None:
        self.span = span
        self.hits: Deque[float] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - self.span
        while self.hits and self.hits[0] <= cutoff:
            self.hits.popleft()

    def take(self, now: float, allowance: int) -> Optional[float]:
        """Records a hit and returns `None`, or refuses and returns the seconds
        until the oldest hit ages out — which is what `Retry-After` wants."""
        self._prune(now)
        if len(self.hits) >= allowance:
            return max(1.0, self.hits[0] + self.span - now)
        self.hits.append(now)
        return None

    def is_idle(self, now: float) -> bool:
        self._prune(now)
        return not self.hits


#: Keyed by client address. Grows with distinct callers, swept in `_take`.
_clients: Dict[str, _RollingWindow] = {}

#: Keyed by provider name. The free tier's daily quota is per model, so a day
#: spent on `gemini` must not close the door on `qwen`. Bounded by the registry,
#: so this one never needs sweeping.
_providers: Dict[str, _RollingWindow] = {}


def _take(
    table: Dict[str, _RollingWindow], key: str, span: float, allowance: int
) -> Optional[float]:
    if allowance <= 0:  # 0 documented as "no limit".
        return None
    now = time.monotonic()
    if table is _clients and len(table) > MAX_TRACKED_CLIENTS:
        _sweep(now)
    window = table.get(key)
    if window is None:
        window = table[key] = _RollingWindow(span)
    return window.take(now, allowance)


def _sweep(now: float) -> None:
    for key in [key for key, window in _clients.items() if window.is_idle(now)]:
        del _clients[key]
    if len(_clients) > MAX_TRACKED_CLIENTS:
        # Every tracked client is currently active and there are thousands of
        # them: either real success or a distributed flood, and this process
        # cannot tell which. Forgive the windows rather than grow without bound —
        # the daily cap below is the limit that still holds.
        logger.warning(
            "rate limit: %d active clients exceeds %d; clearing burst windows",
            len(_clients),
            MAX_TRACKED_CLIENTS,
        )
        _clients.clear()


def limit_request_rate(request: Request) -> None:
    """Route dependency: the per-client burst limit.

    Ordered after `require_api_key` in the route's `dependencies` so an
    unauthenticated caller gets 401 rather than a 429 that would confirm the
    endpoint is real.
    """
    allowance = requests_per_minute()
    identity = client_identity(request)
    retry_after = _take(_clients, identity, MINUTE, allowance)
    if retry_after is None:
        return
    logger.warning(
        "rate limit: %s exceeded %d requests/minute on %s",
        identity,
        allowance,
        request.url.path,
    )
    raise HTTPException(
        status_code=429,
        detail="Quá nhiều yêu cầu. Thử lại sau {:.0f} giây.".format(retry_after),
        headers={"Retry-After": str(int(retry_after))},
    )


def reserve_model_call(provider_name: str) -> None:
    """The daily cap, consumed immediately before a provider is called.

    A reservation is never refunded, including when the provider then fails. An
    upstream 429 or 503 has already spent the quota it is complaining about, and
    for the one case that truly costs nothing — a misconfigured key failing
    before any network call — over-counting is the safe direction for a guard
    whose whole purpose is to not reach the provider's own limit.
    """
    allowance = model_calls_per_day()
    retry_after = _take(_providers, provider_name, DAY, allowance)
    if retry_after is None:
        return
    logger.warning(
        "rate limit: provider %s reached %d model calls/day; %.1f hours until the "
        "oldest ages out",
        provider_name,
        allowance,
        retry_after / 3600.0,
    )
    raise HTTPException(
        status_code=429,
        detail=(
            "Đã đạt giới hạn phân tích trong ngày cho '{}'. Thử lại sau.".format(
                provider_name
            )
        ),
        headers={"Retry-After": str(int(retry_after))},
    )


def status() -> dict:
    """What the limits are and how much of each is spent — so a deploy can be
    checked the way `GET /v1/providers` checks credentials."""
    now = time.monotonic()
    per_minute = requests_per_minute()
    per_day = model_calls_per_day()
    return {
        "requestsPerMinutePerClient": per_minute or None,
        "modelCallsPerDay": per_day or None,
        "trustProxyHeaders": trust_proxy_headers(),
        "trackedClients": len(_clients),
        "modelCallsToday": {
            name: len(window.hits)
            for name, window in _providers.items()
            if not window.is_idle(now)
        },
    }


def reset() -> None:
    """Drops all counters. For tests — module state outlives a single one."""
    _clients.clear()
    _providers.clear()
