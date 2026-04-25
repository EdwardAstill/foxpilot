"""Unit tests for foxpilot.sites.linkedin_service URL/slug/format helpers."""

from __future__ import annotations

import pytest

from foxpilot.sites import linkedin_service as svc


# ---------------------------------------------------------------------------
# is_linkedin_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.linkedin.com/feed/", True),
        ("https://linkedin.com/in/foo/", True),
        ("https://au.linkedin.com/in/foo/", True),
        ("https://example.com/", False),
        ("", False),
        ("not-a-url", False),
    ],
)
def test_is_linkedin_url(value, expected):
    assert svc.is_linkedin_url(value) is expected


# ---------------------------------------------------------------------------
# section_url
# ---------------------------------------------------------------------------

def test_section_url_known():
    assert svc.section_url("feed") == "https://www.linkedin.com/feed/"
    assert svc.section_url("mynetwork") == "https://www.linkedin.com/mynetwork/"
    assert svc.section_url("messaging") == "https://www.linkedin.com/messaging/"
    assert svc.section_url("notifications") == "https://www.linkedin.com/notifications/"
    assert svc.section_url("jobs") == "https://www.linkedin.com/jobs/"


def test_section_url_case_insensitive():
    assert svc.section_url("FEED") == "https://www.linkedin.com/feed/"
    assert svc.section_url("  Jobs  ") == "https://www.linkedin.com/jobs/"


def test_section_url_unknown_raises():
    with pytest.raises(ValueError):
        svc.section_url("nope")
    with pytest.raises(ValueError):
        svc.section_url("")


# ---------------------------------------------------------------------------
# normalize_profile_slug + profile_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("satyanadella", "satyanadella"),
        ("  satyanadella  ", "satyanadella"),
        ("satyanadella/", "satyanadella"),
        ("https://www.linkedin.com/in/satyanadella/", "satyanadella"),
        ("https://www.linkedin.com/in/satyanadella", "satyanadella"),
        ("www.linkedin.com/in/satyanadella/", "satyanadella"),
        ("linkedin.com/in/satyanadella", "satyanadella"),
        ("first-last-1234", "first-last-1234"),
    ],
)
def test_normalize_profile_slug_ok(value, expected):
    assert svc.normalize_profile_slug(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "/",
        "bad slug with spaces",
        "weird!chars",
    ],
)
def test_normalize_profile_slug_bad(value):
    with pytest.raises(ValueError):
        svc.normalize_profile_slug(value)


def test_profile_url():
    assert svc.profile_url("satyanadella") == "https://www.linkedin.com/in/satyanadella/"
    assert (
        svc.profile_url("https://www.linkedin.com/in/satyanadella/")
        == "https://www.linkedin.com/in/satyanadella/"
    )


# ---------------------------------------------------------------------------
# search URL builders
# ---------------------------------------------------------------------------

def test_people_search_url_basic():
    url = svc.people_search_url("rust developer")
    assert url.startswith("https://www.linkedin.com/search/results/people/?")
    assert "keywords=rust+developer" in url


def test_people_search_url_special_chars():
    url = svc.people_search_url("c++ engineer")
    assert "keywords=c%2B%2B+engineer" in url


def test_people_search_url_empty():
    with pytest.raises(ValueError):
        svc.people_search_url("")
    with pytest.raises(ValueError):
        svc.people_search_url("   ")


def test_jobs_search_url_no_location():
    url = svc.jobs_search_url("rust developer")
    assert url.startswith("https://www.linkedin.com/jobs/search/?")
    assert "keywords=rust+developer" in url
    assert "location=" not in url


def test_jobs_search_url_with_location():
    url = svc.jobs_search_url("rust developer", "Perth, Australia")
    assert "keywords=rust+developer" in url
    assert "location=Perth%2C+Australia" in url


def test_jobs_search_url_empty():
    with pytest.raises(ValueError):
        svc.jobs_search_url("")


def test_jobs_search_url_blank_location_ignored():
    url = svc.jobs_search_url("dev", "   ")
    assert "location=" not in url


# ---------------------------------------------------------------------------
# messaging_thread_url
# ---------------------------------------------------------------------------

def test_messaging_thread_url():
    url = svc.messaging_thread_url("abc123")
    assert url == "https://www.linkedin.com/messaging/thread/abc123/"


def test_messaging_thread_url_quoting():
    url = svc.messaging_thread_url("a/b c")
    assert "messaging/thread/a%2Fb%20c/" in url


def test_messaging_thread_url_empty():
    with pytest.raises(ValueError):
        svc.messaging_thread_url("")


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def test_format_open_result():
    out = svc.format_open_result({"title": "T", "url": "U", "section": "feed"})
    assert "title: T" in out
    assert "url: U" in out
    assert "section: feed" in out


def test_format_profile_with_skills():
    data = {
        "name": "X",
        "headline": "H",
        "location": "L",
        "current_role": "R",
        "url": "U",
        "skills": ["a", "b"],
    }
    out = svc.format_profile(data)
    assert "name: X" in out
    assert "headline: H" in out
    assert "skills:" in out
    assert "  - a" in out
    assert "  - b" in out


def test_format_profile_empty():
    assert svc.format_profile({}) == "(no profile data)"


def test_format_people_results_empty():
    assert svc.format_people_results([]) == "(no people results)"


def test_format_people_results_basic():
    out = svc.format_people_results([
        {"name": "A", "headline": "H", "url": "U"},
    ])
    assert "[1] A" in out
    assert "headline: H" in out
    assert "url: U" in out


def test_format_jobs_results_empty():
    assert svc.format_jobs_results([]) == "(no job results)"


def test_format_jobs_results_basic():
    out = svc.format_jobs_results([
        {"title": "T", "company": "C", "location": "L", "url": "U"},
    ])
    assert "[1] T" in out
    assert "company: C" in out


def test_format_threads_empty():
    assert svc.format_threads([]) == "(no message threads)"


def test_format_threads_basic():
    out = svc.format_threads([
        {"peer": "P", "snippet": "S", "when": "W", "thread_id": "T"},
    ])
    assert "[1] P" in out
    assert "snippet: S" in out
    assert "thread: T" in out


# ---------------------------------------------------------------------------
# polite_jitter
# ---------------------------------------------------------------------------

def test_polite_jitter_calls_sleep(monkeypatch):
    captured: list[float] = []
    monkeypatch.setattr(svc.time, "sleep", lambda s: captured.append(s))
    monkeypatch.setattr(svc.random, "random", lambda: 0.5)
    svc.polite_jitter()
    assert captured == [0.5 + 0.5 * 0.5]


def test_polite_jitter_custom(monkeypatch):
    captured: list[float] = []
    monkeypatch.setattr(svc.time, "sleep", lambda s: captured.append(s))
    monkeypatch.setattr(svc.random, "random", lambda: 0.0)
    svc.polite_jitter(min_secs=1.0, spread=2.0)
    assert captured == [1.0]


# ---------------------------------------------------------------------------
# home_url
# ---------------------------------------------------------------------------

def test_home_url():
    assert svc.home_url() == "https://www.linkedin.com/"
