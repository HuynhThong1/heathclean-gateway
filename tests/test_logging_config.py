"""The log format is a contract with whoever reads the logs at 2am."""

import logging
import re

import pytest

from app.logging_config import (
    AccessFormatter,
    DefaultFormatter,
    HealthCheckFilter,
    log_timezone,
    use_colors,
)

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def access_record(path: str = "/v1/meals/analyze", status: int = 200) -> logging.LogRecord:
    """Shaped the way `uvicorn.access` emits them."""
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:56318", "GET", path, "1.1", status),
        exc_info=None,
    )
    return record


class TestTimestamp:
    def test_default_is_utc_plus_seven(self, monkeypatch):
        monkeypatch.delenv("LOG_UTC_OFFSET_HOURS", raising=False)
        assert log_timezone().utcoffset(None).total_seconds() == 7 * 3600

    def test_offset_is_configurable(self, monkeypatch):
        monkeypatch.setenv("LOG_UTC_OFFSET_HOURS", "0")
        assert log_timezone().utcoffset(None).total_seconds() == 0

    def test_a_nonsense_offset_falls_back_rather_than_crashing(self, monkeypatch):
        # Logging must not be the thing that stops the service booting.
        monkeypatch.setenv("LOG_UTC_OFFSET_HOURS", "seven")
        assert log_timezone().utcoffset(None).total_seconds() == 7 * 3600

    def test_the_offset_is_printed_beside_the_time(self, monkeypatch):
        """The whole point: a bare timestamp seven hours out looks plausible."""
        monkeypatch.delenv("LOG_UTC_OFFSET_HOURS", raising=False)
        formatter = DefaultFormatter(fmt="%(asctime)s %(message)s", use_colors=False)
        line = formatter.format(
            logging.LogRecord("app", logging.INFO, __file__, 1, "started", None, None)
        )
        assert "+0700" in line
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \+0700 started", line)


class TestColour:
    def test_colour_can_be_forced_on_for_a_container(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("LOG_COLORS", "1")
        assert use_colors() is True

    def test_colour_can_be_turned_off_for_a_file(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("LOG_COLORS", "0")
        assert use_colors() is False

    def test_no_color_wins(self, monkeypatch):
        """The convention exists so one variable silences every tool."""
        monkeypatch.setenv("LOG_COLORS", "1")
        monkeypatch.setenv("NO_COLOR", "1")
        assert use_colors() is False

    def test_a_plain_formatter_emits_no_escapes(self):
        formatter = AccessFormatter(
            fmt='%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            use_colors=False,
        )
        line = formatter.format(access_record())
        assert ANSI.search(line) is None, "stored logs must not carry escapes"

    def test_a_coloured_formatter_does(self):
        formatter = AccessFormatter(fmt="%(asctime)s %(message)s", use_colors=True)
        assert ANSI.search(formatter.format(access_record())) is not None


class TestHealthCheckFilter:
    def test_a_successful_healthcheck_is_dropped(self, monkeypatch):
        monkeypatch.delenv("LOG_HEALTHZ", raising=False)
        assert HealthCheckFilter().filter(access_record("/healthz", 200)) is False

    @pytest.mark.parametrize("status", [500, 503])
    def test_a_failing_healthcheck_is_kept(self, monkeypatch, status):
        """A probe that started failing is the most useful line in the file."""
        monkeypatch.delenv("LOG_HEALTHZ", raising=False)
        assert HealthCheckFilter().filter(access_record("/healthz", status)) is True

    def test_real_traffic_is_never_dropped(self, monkeypatch):
        monkeypatch.delenv("LOG_HEALTHZ", raising=False)
        assert HealthCheckFilter().filter(access_record("/v1/meals/analyze", 200)) is True

    def test_it_can_be_turned_back_on(self, monkeypatch):
        monkeypatch.setenv("LOG_HEALTHZ", "1")
        assert HealthCheckFilter().filter(access_record("/healthz", 200)) is True

    def test_a_record_it_does_not_recognise_is_kept(self, monkeypatch):
        """Filters must fail open. Losing a line is worse than printing one."""
        monkeypatch.delenv("LOG_HEALTHZ", raising=False)
        record = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1, "something else", None, None
        )
        assert HealthCheckFilter().filter(record) is True
