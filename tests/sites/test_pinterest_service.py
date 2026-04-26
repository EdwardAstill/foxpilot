"""Unit tests for foxpilot.sites.pinterest_service URL/format helpers."""

from __future__ import annotations

import pytest

from foxpilot.sites import pinterest_service as svc


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.pinterest.com/", True),
        ("https://pinterest.com/nasa/", True),
        ("https://au.pinterest.com/nasa/", True),
        ("https://example.com/", False),
        ("", False),
        ("not-a-url", False),
    ],
)
def test_is_pinterest_url(value, expected):
    assert svc.is_pinterest_url(value) is expected


@pytest.mark.parametrize(
    "section,expected",
    [
        ("home", "https://www.pinterest.com/"),
        ("today", "https://www.pinterest.com/ideas/"),
        ("explore", "https://www.pinterest.com/ideas/"),
        ("following", "https://www.pinterest.com/following/"),
        ("notifications", "https://www.pinterest.com/news/"),
    ],
)
def test_section_url(section, expected):
    assert svc.section_url(section) == expected


def test_section_url_unknown_raises():
    with pytest.raises(ValueError):
        svc.section_url("nope")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("nasa", "nasa"),
        ("@nasa", "nasa"),
        ("/nasa/", "nasa"),
        ("https://www.pinterest.com/nasa/", "nasa"),
        ("https://pinterest.com/nasa/space/", "nasa"),
        ("pinterest.com/nasa", "nasa"),
    ],
)
def test_normalize_username(raw, expected):
    assert svc.normalize_username(raw) == expected


@pytest.mark.parametrize("bad", ["", "   ", "@", "/", "in valid", "with spaces"])
def test_normalize_username_invalid(bad):
    with pytest.raises(ValueError):
        svc.normalize_username(bad)


def test_profile_url():
    assert svc.profile_url("nasa") == "https://www.pinterest.com/nasa/"
    assert svc.profile_url("@nasa") == "https://www.pinterest.com/nasa/"


def test_board_url():
    assert (
        svc.board_url("nasa", "space-exploration")
        == "https://www.pinterest.com/nasa/space-exploration/"
    )


def test_board_url_empty_slug():
    with pytest.raises(ValueError):
        svc.board_url("nasa", "")


def test_pin_url():
    assert svc.pin_url("123456789") == "https://www.pinterest.com/pin/123456789/"


def test_pin_url_empty():
    with pytest.raises(ValueError):
        svc.pin_url("")


def test_search_url():
    url = svc.search_url("minimalist living room")
    assert url.startswith("https://www.pinterest.com/search/pins/?q=")
    assert "minimalist+living+room" in url


def test_search_url_empty():
    with pytest.raises(ValueError):
        svc.search_url("   ")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("123456789", "https://www.pinterest.com/pin/123456789/"),
        ("/pin/123456789/", "https://www.pinterest.com/pin/123456789/"),
        ("pin/123456789", "https://www.pinterest.com/pin/123456789/"),
        ("https://www.pinterest.com/pin/123456789/", "https://www.pinterest.com/pin/123456789/"),
    ],
)
def test_normalize_pin_target(raw, expected):
    assert svc.normalize_pin_target(raw) == expected


def test_normalize_pin_target_invalid():
    with pytest.raises(ValueError):
        svc.normalize_pin_target("not-a-pin")


def test_format_open_result():
    text = svc.format_open_result({"title": "Pinterest", "url": "https://x", "section": "today"})
    assert "title: Pinterest" in text
    assert "section: today" in text


def test_format_profile_empty():
    assert svc.format_profile({}) == "(no profile data)"


def test_format_profile_renders_known_fields():
    text = svc.format_profile({"username": "nasa", "name": "NASA", "followers": "1M"})
    assert "username: nasa" in text
    assert "name: NASA" in text
    assert "followers: 1M" in text


def test_format_pins_empty():
    assert svc.format_pins([]) == "(no pins)"


def test_format_pins_renders():
    text = svc.format_pins([{"title": "T", "url": "https://x", "pin_id": "1"}])
    assert "[1] T" in text
    assert "url: https://x" in text


def test_format_boards_empty():
    assert svc.format_boards([]) == "(no boards)"


def test_format_search_results_empty():
    assert svc.format_search_results([]) == "(no search results)"
