"""Unit tests for foxpilot.sites.gcal_service URL/date helpers."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from foxpilot.sites import gcal_service as svc


# --- is_gcal_url ------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://calendar.google.com/", True),
        ("https://calendar.google.com/calendar/u/0/r/week", True),
        ("https://www.calendar.google.com/", True),
        ("https://mail.google.com/", False),
        ("https://example.com/", False),
        ("", False),
    ],
)
def test_is_gcal_url(url, expected):
    assert svc.is_gcal_url(url) is expected


# --- format_compact_date ----------------------------------------------------


def test_format_compact_date():
    assert svc.format_compact_date(date(2026, 4, 25)) == "20260425"
    assert svc.format_compact_date(date(2026, 1, 1)) == "20260101"


def test_format_compact_datetime():
    assert svc.format_compact_datetime(datetime(2026, 4, 25, 12, 30, 0)) == "20260425T123000"


# --- view_url ---------------------------------------------------------------


@pytest.mark.parametrize("view", ["day", "week", "month", "agenda"])
def test_view_url_basic(view):
    url = svc.view_url(view)
    assert url == f"https://calendar.google.com/calendar/u/0/r/{view}"


def test_view_url_with_date_appends_dates_qs():
    url = svc.view_url("week", on=date(2026, 4, 25))
    assert url == "https://calendar.google.com/calendar/u/0/r/week?dates=20260425"


def test_view_url_rejects_unknown_view():
    with pytest.raises(ValueError):
        svc.view_url("year")


# --- date_range_url ---------------------------------------------------------


def test_date_range_url_single_date():
    url = svc.date_range_url("agenda", date(2026, 4, 25))
    assert url == "https://calendar.google.com/calendar/u/0/r/agenda?dates=20260425"


def test_date_range_url_two_dates():
    url = svc.date_range_url("agenda", date(2026, 4, 25), date(2026, 5, 2))
    assert url == "https://calendar.google.com/calendar/u/0/r/agenda?dates=20260425/20260502"


def test_date_range_url_rejects_inverted():
    with pytest.raises(ValueError):
        svc.date_range_url("agenda", date(2026, 5, 2), date(2026, 4, 25))


def test_date_range_url_rejects_unknown_view():
    with pytest.raises(ValueError):
        svc.date_range_url("year", date(2026, 4, 25))


# --- search_url -------------------------------------------------------------


def test_search_url_encodes_query():
    url = svc.search_url("standup tomorrow")
    assert url.startswith("https://calendar.google.com/calendar/u/0/r/search?")
    assert "q=standup+tomorrow" in url


# --- event_create_url -------------------------------------------------------


def test_event_create_url_minimal():
    url = svc.event_create_url(title="Lunch")
    assert url.startswith("https://calendar.google.com/calendar/render?")
    assert "action=TEMPLATE" in url
    assert "text=Lunch" in url


def test_event_create_url_with_when_and_duration():
    url = svc.event_create_url(title="Lunch", when="2026-04-25 12:30", duration_minutes=45)
    assert "dates=20260425T123000%2F20260425T131500" in url


def test_event_create_url_with_invitees_location_details():
    url = svc.event_create_url(
        title="Sync",
        when="2026-04-25 14:00",
        duration_minutes=30,
        invitees=["alice@example.com", "bob@example.com"],
        location="Room 3",
        details="catch up",
    )
    assert "add=alice%40example.com%2Cbob%40example.com" in url
    assert "location=Room+3" in url
    assert "details=catch+up" in url


def test_event_create_url_skips_blank_invitees():
    url = svc.event_create_url(title="x", when="2026-04-25", invitees=["", "  "])
    assert "add=" not in url


# --- parse_date -------------------------------------------------------------


def test_parse_date_iso():
    assert svc.parse_date("2026-04-25") == date(2026, 4, 25)


def test_parse_date_compact():
    assert svc.parse_date("20260425") == date(2026, 4, 25)


def test_parse_date_today_uses_anchor():
    anchor = date(2026, 4, 25)
    assert svc.parse_date("today", today=anchor) == anchor
    assert svc.parse_date("tomorrow", today=anchor) == date(2026, 4, 26)
    assert svc.parse_date("yesterday", today=anchor) == date(2026, 4, 24)


def test_parse_date_offsets():
    anchor = date(2026, 4, 25)
    assert svc.parse_date("+7d", today=anchor) == date(2026, 5, 2)
    assert svc.parse_date("-3d", today=anchor) == date(2026, 4, 22)


def test_parse_date_invalid():
    with pytest.raises(ValueError):
        svc.parse_date("not-a-date")
    with pytest.raises(ValueError):
        svc.parse_date("")


# --- parse_when -------------------------------------------------------------


def test_parse_when_full():
    assert svc.parse_when("2026-04-25 12:30") == datetime(2026, 4, 25, 12, 30)
    assert svc.parse_when("2026-04-25T12:30") == datetime(2026, 4, 25, 12, 30)


def test_parse_when_date_only_defaults_morning():
    assert svc.parse_when("2026-04-25") == datetime(2026, 4, 25, 9, 0)


def test_parse_when_invalid():
    with pytest.raises(ValueError):
        svc.parse_when("nope")


# --- formatters -------------------------------------------------------------


def test_format_open_result():
    out = svc.format_open_result({"title": "X", "url": "u", "view": "week"})
    assert "title: X" in out and "url: u" in out and "view: week" in out


def test_format_events_empty():
    assert svc.format_events([]) == "(no events)"


def test_format_events_lines():
    out = svc.format_events([{"title": "Standup", "when": "09:00", "calendar": "Work"}])
    assert "Standup" in out and "09:00" in out and "[Work]" in out


def test_format_event_detail_skips_blank():
    out = svc.format_event_detail({"title": "X", "description": "", "guests": []})
    assert "title: X" in out
    assert "description" not in out


def test_format_event_detail_empty():
    assert svc.format_event_detail({}) == "(no event detail)"
