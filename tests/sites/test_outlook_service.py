"""Unit tests for foxpilot.sites.outlook_service URL helpers and formatters."""

from __future__ import annotations

import json

import pytest

from foxpilot.sites import outlook_service as svc


class TestNormalizeFolder:
    def test_default_inbox(self):
        assert svc.normalize_folder("inbox") == "inbox"

    def test_aliases(self):
        assert svc.normalize_folder("Sent-Items") == "sent"
        assert svc.normalize_folder("OUTBOX") == "sent"
        assert svc.normalize_folder("Draft") == "drafts"
        assert svc.normalize_folder("archived") == "archive"

    def test_blank_falls_back_to_inbox(self):
        assert svc.normalize_folder("") == "inbox"

    def test_unknown_raises(self):
        with pytest.raises(ValueError) as exc:
            svc.normalize_folder("spam")
        assert "spam" in str(exc.value)


class TestBuildFolderUrl:
    def test_inbox(self):
        assert svc.build_folder_url("inbox") == "https://outlook.office.com/mail/inbox"

    def test_sent_uses_sentitems_segment(self):
        assert svc.build_folder_url("sent") == "https://outlook.office.com/mail/sentitems"

    def test_drafts(self):
        assert svc.build_folder_url("drafts") == "https://outlook.office.com/mail/drafts"

    def test_archive(self):
        assert svc.build_folder_url("archive") == "https://outlook.office.com/mail/archive"


class TestBuildSearchUrl:
    def test_basic(self):
        url = svc.build_search_url("project alpha")
        assert url == "https://outlook.office.com/mail/inbox/search/query=project%20alpha"

    def test_in_sent(self):
        url = svc.build_search_url("budget", folder="sent")
        assert url.startswith("https://outlook.office.com/mail/sentitems/search/query=")
        assert "budget" in url

    def test_special_chars_encoded(self):
        url = svc.build_search_url("from:advisor@uwa.edu.au")
        assert "from%3Aadvisor%40uwa.edu.au" in url

    def test_empty_query_raises(self):
        with pytest.raises(ValueError):
            svc.build_search_url("   ")


class TestBuildCalendarUrl:
    @pytest.mark.parametrize("view", ["day", "week", "workweek", "month"])
    def test_valid_views(self, view):
        assert svc.build_calendar_url(view) == f"https://outlook.office.com/calendar/view/{view}"

    def test_default_week(self):
        assert svc.build_calendar_url() == "https://outlook.office.com/calendar/view/week"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            svc.build_calendar_url("year")


class TestIsOutlookUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://outlook.office.com/mail/inbox",
            "https://outlook.office365.com/owa/",
            "https://outlook.live.com/mail/0/",
        ],
    )
    def test_matches(self, url):
        assert svc.is_outlook_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://gmail.google.com/",
            "https://example.com/",
            "",
        ],
    )
    def test_rejects(self, url):
        assert not svc.is_outlook_url(url)


class TestNormalizeOutlookTarget:
    def test_folder_name(self):
        assert svc.normalize_outlook_target("inbox") == "https://outlook.office.com/mail/inbox"

    def test_full_url_passthrough(self):
        url = "https://outlook.office.com/mail/sentitems"
        assert svc.normalize_outlook_target(url) == url

    def test_bare_host_url(self):
        url = svc.normalize_outlook_target("outlook.office.com/mail/inbox")
        assert url.startswith("https://outlook.office.com/")

    def test_non_outlook_url_raises(self):
        with pytest.raises(ValueError):
            svc.normalize_outlook_target("https://gmail.google.com/")


class TestParseRecipients:
    def test_none(self):
        assert svc.parse_recipients(None) == []

    def test_blank(self):
        assert svc.parse_recipients("   ") == []

    def test_comma_split(self):
        assert svc.parse_recipients("a@b.com, c@d.com") == ["a@b.com", "c@d.com"]

    def test_semicolon_split(self):
        assert svc.parse_recipients("a@b.com; c@d.com") == ["a@b.com", "c@d.com"]

    def test_mixed_and_strips(self):
        assert svc.parse_recipients(" a@b.com ,; c@d.com ;") == ["a@b.com", "c@d.com"]


class TestFormatters:
    def test_format_open_result(self):
        out = svc.format_open_result(
            {"title": "Outlook", "url": "https://outlook.office.com/mail/inbox", "folder": "inbox"}
        )
        assert "title: Outlook" in out
        assert "folder: inbox" in out

    def test_format_messages_empty(self):
        assert "No Outlook messages" in svc.format_messages([])

    def test_format_messages_basic(self):
        items = [
            {"subject": "Hello", "from": "a@b.com", "snippet": "hi", "unread": True},
            {"subject": "World", "from": "c@d.com", "snippet": "yo", "unread": False},
        ]
        text = svc.format_messages(items)
        assert "Hello" in text
        assert "World" in text
        assert text.startswith("*")  # first item is unread

    def test_format_message_detail(self):
        out = svc.format_message_detail(
            {"subject": "Hi", "from": "a@b.com", "to": "c@d.com", "body": "Body text"}
        )
        assert "subject: Hi" in out
        assert "Body text" in out

    def test_format_calendar_empty(self):
        assert "No Outlook calendar" in svc.format_calendar([])

    def test_format_calendar_basic(self):
        events = [{"title": "Meeting", "when": "Tue 10:00", "location": "Room 3"}]
        out = svc.format_calendar(events)
        assert "Meeting" in out
        assert "Room 3" in out

    def test_format_compose_result(self):
        out = svc.format_compose_result(
            {"status": "drafted", "to": ["a@b.com"], "subject": "hi", "url": "x"}
        )
        assert "status: drafted" in out
        assert "to: a@b.com" in out

    def test_format_send_result(self):
        out = svc.format_send_result({"status": "sent", "url": "https://x"})
        assert "status: sent" in out

    def test_to_json_roundtrip(self):
        payload = {"a": 1, "b": [1, 2]}
        text = svc.to_json(payload)
        assert json.loads(text) == payload


class TestConstants:
    def test_home_urls(self):
        assert svc.OUTLOOK_MAIL_HOME == "https://outlook.office.com/mail/"
        assert svc.OUTLOOK_CALENDAR_HOME == "https://outlook.office.com/calendar/"
