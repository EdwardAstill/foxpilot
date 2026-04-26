"""Unit tests for foxpilot.sites.reddit_service URL/format helpers."""

from __future__ import annotations

import pytest

from foxpilot.sites import reddit_service as svc


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.reddit.com/", True),
        ("https://reddit.com/r/python/", True),
        ("https://old.reddit.com/r/python/", True),
        ("https://example.com/", False),
        ("", False),
    ],
)
def test_is_reddit_url(value, expected):
    assert svc.is_reddit_url(value) is expected


@pytest.mark.parametrize(
    "section,expected",
    [
        ("home", "https://www.reddit.com/"),
        ("popular", "https://www.reddit.com/r/popular/"),
        ("all", "https://www.reddit.com/r/all/"),
        ("saved", "https://www.reddit.com/saved/"),
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
        ("python", "python"),
        ("r/python", "python"),
        ("/r/python/", "python"),
        ("Python_Tips", "Python_Tips"),
    ],
)
def test_normalize_subreddit(raw, expected):
    assert svc.normalize_subreddit(raw) == expected


@pytest.mark.parametrize("bad", ["", "   ", "in valid"])
def test_normalize_subreddit_invalid(bad):
    with pytest.raises(ValueError):
        svc.normalize_subreddit(bad)


def test_subreddit_url_default_sort():
    assert svc.subreddit_url("python") == "https://www.reddit.com/r/python/hot/"


def test_subreddit_url_with_sort():
    assert svc.subreddit_url("python", sort="new") == "https://www.reddit.com/r/python/new/"


def test_subreddit_url_invalid_sort():
    with pytest.raises(ValueError):
        svc.subreddit_url("python", sort="weekly")


def test_post_url_from_id():
    assert svc.post_url_from_id("abc123") == "https://www.reddit.com/comments/abc123/"


def test_post_url_from_id_empty():
    with pytest.raises(ValueError):
        svc.post_url_from_id("")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("abc123", "https://www.reddit.com/comments/abc123/"),
        ("/comments/abc123/", "https://www.reddit.com/comments/abc123/"),
        ("comments/abc123", "https://www.reddit.com/comments/abc123"),
        ("https://www.reddit.com/r/python/comments/abc123/", "https://www.reddit.com/r/python/comments/abc123/"),
    ],
)
def test_normalize_post_target(raw, expected):
    assert svc.normalize_post_target(raw) == expected


def test_search_url_no_sub():
    url = svc.search_url("rust async")
    assert url.startswith("https://www.reddit.com/search/?")
    assert "q=rust+async" in url


def test_search_url_with_sub():
    url = svc.search_url("async", subreddit="python")
    assert "/r/python/search/" in url
    assert "restrict_sr=1" in url


def test_search_url_empty_query():
    with pytest.raises(ValueError):
        svc.search_url("   ")


def test_format_open_result():
    text = svc.format_open_result({"title": "Reddit", "url": "https://x", "section": "popular"})
    assert "title: Reddit" in text
    assert "section: popular" in text


def test_format_posts_empty():
    assert svc.format_posts([]) == "(no posts)"


def test_format_posts_renders():
    text = svc.format_posts([
        {"title": "Hello", "subreddit": "r/python", "author": "alice", "url": "https://x"},
    ])
    assert "[1] Hello" in text
    assert "subreddit: r/python" in text
    assert "url: https://x" in text


def test_format_post_empty():
    assert svc.format_post({}) == "(no post data)"


def test_format_post_truncates_long_text():
    long = "y" * 600
    text = svc.format_post({"title": "T", "text": long})
    assert "title: T" in text
    assert "…" in text
