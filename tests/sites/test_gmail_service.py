"""Unit tests for the Gmail service layer (URL + formatter helpers)."""

from __future__ import annotations

import unittest

from foxpilot.sites.gmail_service import (
    GMAIL_HOME,
    GMAIL_HOST,
    build_gmail_search_url,
    format_action_result,
    format_compose_result,
    format_message_detail,
    format_message_list,
    format_open_result,
    is_gmail_url,
    label_url,
    looks_like_thread_id,
    normalize_thread_id,
)


class GmailUrlHelperTests(unittest.TestCase):
    def test_is_gmail_url_recognises_canonical_host(self):
        self.assertTrue(is_gmail_url("https://mail.google.com/mail/u/0/#inbox"))
        self.assertTrue(is_gmail_url("https://mail.google.com/"))

    def test_is_gmail_url_rejects_other_hosts(self):
        self.assertFalse(is_gmail_url("https://gmail.com/mail"))
        self.assertFalse(is_gmail_url("https://google.com/mail"))
        self.assertFalse(is_gmail_url(""))

    def test_label_url_defaults_to_inbox(self):
        self.assertEqual(label_url(None), GMAIL_HOME)
        self.assertEqual(label_url(""), GMAIL_HOME)
        self.assertEqual(label_url("   "), GMAIL_HOME)

    def test_label_url_resolves_system_labels_case_insensitive(self):
        self.assertEqual(
            label_url("Starred"),
            f"https://{GMAIL_HOST}/mail/u/0/#starred",
        )
        self.assertEqual(
            label_url("important"),
            f"https://{GMAIL_HOST}/mail/u/0/#imp",
        )
        self.assertEqual(
            label_url("Trash"),
            f"https://{GMAIL_HOST}/mail/u/0/#trash",
        )

    def test_label_url_treats_unknown_as_user_label(self):
        url = label_url("Work/Reports")
        self.assertTrue(url.startswith(f"https://{GMAIL_HOST}/mail/u/0/#label/"))
        self.assertIn("Work/Reports", url)

    def test_build_gmail_search_url_encodes_query(self):
        url = build_gmail_search_url("from:alice has:attachment")
        self.assertTrue(
            url.startswith(f"https://{GMAIL_HOST}/mail/u/0/#search/"),
            url,
        )
        self.assertIn("from%3Aalice", url)
        self.assertIn("has%3Aattachment", url)

    def test_build_gmail_search_url_rejects_empty(self):
        with self.assertRaises(ValueError):
            build_gmail_search_url("")
        with self.assertRaises(ValueError):
            build_gmail_search_url("   ")


class GmailIdHelperTests(unittest.TestCase):
    def test_normalize_thread_id_strips_whitespace(self):
        self.assertEqual(normalize_thread_id("  abc123  "), "abc123")

    def test_normalize_thread_id_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_thread_id("   ")

    def test_looks_like_thread_id_accepts_alnum(self):
        self.assertTrue(looks_like_thread_id("186a4f9c0123abcd"))
        self.assertTrue(looks_like_thread_id("abcdef12"))

    def test_looks_like_thread_id_rejects_search_strings(self):
        self.assertFalse(looks_like_thread_id("from:alice"))
        self.assertFalse(looks_like_thread_id("hi there"))
        self.assertFalse(looks_like_thread_id("short"))


class GmailFormatterTests(unittest.TestCase):
    def test_format_open_result(self):
        out = format_open_result(
            {"title": "Inbox", "url": "https://mail.google.com/", "label": "inbox"}
        )
        self.assertIn("title: Inbox", out)
        self.assertIn("label: inbox", out)
        self.assertIn("url: https://mail.google.com/", out)

    def test_format_message_list_empty(self):
        self.assertEqual(format_message_list([]), "(no messages found)")

    def test_format_message_list_marks_unread_and_includes_id(self):
        out = format_message_list(
            [
                {
                    "id": "abc123",
                    "from": "Alice",
                    "subject": "Hi",
                    "snippet": "hello there",
                    "age": "2d",
                    "unread": True,
                },
                {
                    "id": "def456",
                    "from": "Bob",
                    "subject": "FYI",
                    "snippet": "",
                    "age": "1h",
                    "unread": False,
                },
            ]
        )
        # First entry unread → starts with '*' marker
        first_line = out.splitlines()[0]
        self.assertTrue(first_line.startswith("*"), first_line)
        self.assertIn("Alice", out)
        self.assertIn("Hi", out)
        self.assertIn("id: abc123", out)
        self.assertIn("id: def456", out)
        self.assertIn("Bob", out)

    def test_format_message_detail_uses_headers_and_body(self):
        out = format_message_detail(
            {
                "subject": "Quarterly review",
                "headers": {
                    "from": "alice@example.com",
                    "to": "team@example.com",
                    "date": "Apr 23 2026",
                },
                "body": "Hi team",
                "url": "https://mail.google.com/x",
            }
        )
        self.assertIn("subject: Quarterly review", out)
        self.assertIn("from: alice@example.com", out)
        self.assertIn("to: team@example.com", out)
        self.assertIn("date: Apr 23 2026", out)
        self.assertIn("Hi team", out)

    def test_format_compose_result_reports_body_chars(self):
        out = format_compose_result(
            {"state": "filled", "to": "a@b.com", "subject": "Hi", "body": "hello"}
        )
        self.assertIn("compose: filled", out)
        self.assertIn("to: a@b.com", out)
        self.assertIn("subject: Hi", out)
        self.assertIn("body_chars: 5", out)

    def test_format_action_result(self):
        out = format_action_result(
            {"action": "delete", "target": "abc", "result": "clicked"}
        )
        self.assertIn("action: delete", out)
        self.assertIn("target: abc", out)
        self.assertIn("result: clicked", out)


if __name__ == "__main__":
    unittest.main()
