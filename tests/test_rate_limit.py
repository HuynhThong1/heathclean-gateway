"""The two limits that keep a leaked key from costing a day of service.

Both are read per request, so `monkeypatch.setenv` is enough — no reimporting
the app. `conftest.py` disables them for the rest of the suite; every test here
sets the value it needs.

`TestClient` reports one client address (`testclient`) for every request, which
is what makes the burst tests work: they are all "the same caller" unless a test
says otherwise with `X-Forwarded-For`.
"""

import io

import pytest
from fastapi.testclient import TestClient

from app import rate_limit
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_counters():
    # Module state outlives a test, and a rolling window measured in days will
    # not age out on its own inside a suite.
    rate_limit.reset()
    yield
    rate_limit.reset()


def _image():
    return {"image": ("meal.jpg", io.BytesIO(b"plate-0000"), "image/jpeg")}


def _analyze(**kwargs):
    return client.post("/v1/meals/analyze", files=_image(), **kwargs)


# --- the per-client burst limit ------------------------------------------------


def test_requests_under_the_burst_limit_all_pass(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    assert [_analyze().status_code for _ in range(3)] == [200, 200, 200]


def test_the_request_after_the_burst_limit_is_refused(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    _analyze()
    _analyze()
    response = _analyze()
    assert response.status_code == 429
    # A client that cannot tell *how long* has to guess, and guessing turns into
    # a retry loop that keeps the window full.
    assert int(response.headers["Retry-After"]) > 0


def test_zero_means_no_limit(monkeypatch):
    # Documented in `.env.example`: the escape hatch for a private deployment.
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    assert [_analyze().status_code for _ in range(12)] == [200] * 12


def test_an_unparseable_limit_falls_back_to_the_default(monkeypatch):
    # A typo in `.env` must not take the service down, and it must not silently
    # remove the limit either.
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "ten")
    assert rate_limit.requests_per_minute() == rate_limit.DEFAULT_PER_MINUTE


def test_authentication_answers_before_the_limiter(monkeypatch):
    # A 429 to an unauthenticated caller would confirm the endpoint is real and
    # being used. 401 tells them nothing.
    monkeypatch.setenv("GATEWAY_API_KEY", "s3cret")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    assert [_analyze().status_code for _ in range(3)] == [401, 401, 401]
    # And nothing was counted against the real caller's allowance.
    assert _analyze(headers={"X-API-Key": "s3cret"}).status_code == 200


# --- whose address is it -------------------------------------------------------


def test_forwarded_for_is_ignored_unless_the_proxy_is_trusted(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    assert _analyze().status_code == 200
    # Without a trusted proxy the header is just something the caller typed, so
    # a new value must not buy a new allowance.
    assert _analyze(headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 429


def test_a_trusted_proxy_separates_clients(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    assert _analyze(headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert _analyze(headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 429
    # A different phone behind the same proxy is a different caller.
    assert _analyze(headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 200


def test_a_client_cannot_prepend_its_way_out_of_the_limit(monkeypatch):
    # The proxy *appends* the peer it spoke to, so the last entry is the only one
    # the caller did not choose. Reading the conventional left-most entry would
    # hand out a fresh window per made-up address.
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    assert _analyze(headers={"X-Forwarded-For": "198.51.100.7"}).status_code == 200
    spoofed = {"X-Forwarded-For": "10.9.9.9, 198.51.100.7"}
    assert _analyze(headers=spoofed).status_code == 429


# --- the daily cap on model calls ---------------------------------------------


def test_the_daily_cap_stops_further_model_calls(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "2")
    assert [_analyze().status_code for _ in range(2)] == [200, 200]
    response = _analyze()
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_a_rejected_request_never_spends_a_days_allowance(monkeypatch):
    # The whole reason this one is consumed in the handler rather than as a
    # dependency: a PDF costs the provider nothing, so it must not cost quota.
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "1")
    rejected = client.post(
        "/v1/meals/analyze",
        files={"image": ("meal.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert rejected.status_code == 415
    assert _analyze().status_code == 200


def test_the_cap_is_per_provider_because_the_quota_is(monkeypatch):
    # A day spent on one model must not close the door on another — the free
    # tier's daily quota is per model (README, "Model names rot").
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "1")
    assert _analyze().status_code == 200
    assert _analyze().status_code == 429
    # 502 here, not 200: `gemini` has no key in the suite. What matters is that
    # it was allowed to try at all.
    other = _analyze(headers={"X-Model-Provider": "gemini"})
    assert other.status_code == 502


def test_status_reports_the_limits_and_what_is_spent(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "50")
    _analyze()
    reported = client.get("/v1/providers").json()["rateLimit"]
    assert reported["requestsPerMinutePerClient"] == 5
    assert reported["modelCallsPerDay"] == 50
    assert reported["modelCallsToday"]["mock"] == 1
    # `null` rather than `0`, so a client reading it cannot mistake "no limit"
    # for "no requests left".
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "0")
    assert client.get("/v1/providers").json()["rateLimit"]["modelCallsPerDay"] is None
