"""Unit tests for foxpilot.sites.figma_service URL/format helpers."""

from __future__ import annotations

import pytest

from foxpilot.sites import figma_service as svc


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.figma.com/", True),
        ("https://figma.com/file/abc/", True),
        ("https://example.com/", False),
        ("", False),
    ],
)
def test_is_figma_url(value, expected):
    assert svc.is_figma_url(value) is expected


def test_home_url():
    assert svc.home_url() == "https://www.figma.com/"


def test_files_url():
    assert svc.files_url() == "https://www.figma.com/files/recents-and-sharing"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ABCdef12345", "https://www.figma.com/file/ABCdef12345/"),
        ("abc-DEF_123456", "https://www.figma.com/file/abc-DEF_123456/"),
        ("https://www.figma.com/file/XYZ/Title", "https://www.figma.com/file/XYZ/Title"),
        ("/file/XYZ/", "https://www.figma.com/file/XYZ/"),
    ],
)
def test_file_url(raw, expected):
    assert svc.file_url(raw) == expected


@pytest.mark.parametrize("bad", ["", "   ", "abc", "with spaces", "abc!@#"])
def test_file_url_invalid(bad):
    with pytest.raises(ValueError):
        svc.file_url(bad)


def test_search_url():
    url = svc.search_url("design system")
    assert url.startswith("https://www.figma.com/search?")
    assert "design+system" in url


def test_search_url_empty():
    with pytest.raises(ValueError):
        svc.search_url("   ")


def test_format_open_result():
    text = svc.format_open_result({"title": "Figma", "url": "https://x"})
    assert "title: Figma" in text


def test_format_file_empty():
    assert svc.format_file({}) == "(no file data)"


def test_format_file_renders():
    text = svc.format_file({"name": "Mockups", "team": "Design", "url": "https://x"})
    assert "name: Mockups" in text
    assert "team: Design" in text


def test_format_files_empty():
    assert svc.format_files([]) == "(no files)"


def test_format_files_renders():
    text = svc.format_files([{"name": "Mockups", "url": "https://x"}])
    assert "[1] Mockups" in text
    assert "url: https://x" in text


def test_format_search_results_delegates():
    assert svc.format_search_results([]) == "(no files)"
