"""Unit tests for foxpilot.sites.teams_service URL/section helpers + formatters."""

from __future__ import annotations

import json
import unittest

from foxpilot.sites.teams_service import (
    TEAMS_HOME,
    TEAMS_SECTIONS,
    build_teams_url,
    format_chats,
    format_messages,
    format_open_result,
    format_post_result,
    format_teams_list,
    is_teams_url,
    normalize_section,
    normalize_teams_target,
    to_json,
)


class TeamsSectionTests(unittest.TestCase):
    def test_known_sections_registered(self):
        for name in ("chat", "teams", "calendar", "calls", "activity"):
            self.assertIn(name, TEAMS_SECTIONS)

    def test_normalize_section_aliases(self):
        self.assertEqual(normalize_section("messages"), "chat")
        self.assertEqual(normalize_section("conversation"), "chat")
        self.assertEqual(normalize_section("CHANNELS"), "teams")
        self.assertEqual(normalize_section("schedule"), "calendar")
        self.assertEqual(normalize_section("notifications"), "activity")
        self.assertEqual(normalize_section("call"), "calls")

    def test_normalize_section_default(self):
        self.assertEqual(normalize_section(""), "chat")

    def test_normalize_section_unknown_errors(self):
        with self.assertRaisesRegex(ValueError, "unknown Teams section"):
            normalize_section("zzzzz")


class TeamsUrlTests(unittest.TestCase):
    def test_build_teams_url_chat_default(self):
        self.assertEqual(build_teams_url("chat"), f"{TEAMS_HOME}_#/conversations")

    def test_build_teams_url_calendar(self):
        self.assertEqual(build_teams_url("calendar"), f"{TEAMS_HOME}_#/calendarv2")

    def test_build_teams_url_teams_section(self):
        self.assertEqual(build_teams_url("teams"), f"{TEAMS_HOME}_#/discover")

    def test_is_teams_url(self):
        self.assertTrue(is_teams_url("https://teams.microsoft.com/_#/conversations"))
        self.assertTrue(is_teams_url("teams.microsoft.com/foo"))
        self.assertFalse(is_teams_url("https://example.com/"))
        self.assertFalse(is_teams_url(""))

    def test_normalize_teams_target_section_name(self):
        self.assertEqual(normalize_teams_target("calendar"), f"{TEAMS_HOME}_#/calendarv2")

    def test_normalize_teams_target_url_passthrough(self):
        url = "https://teams.microsoft.com/_#/calendarv2"
        self.assertEqual(normalize_teams_target(url), url)

    def test_normalize_teams_target_rejects_non_teams_url(self):
        with self.assertRaisesRegex(ValueError, "not a Teams URL"):
            normalize_teams_target("https://example.com/foo")


class TeamsFormatterTests(unittest.TestCase):
    def test_format_open_result(self):
        out = format_open_result({"title": "Chat | Teams", "url": "https://teams.microsoft.com/", "section": "chat"})
        self.assertIn("title: Chat | Teams", out)
        self.assertIn("url: https://teams.microsoft.com/", out)
        self.assertIn("section: chat", out)

    def test_format_chats_empty(self):
        self.assertEqual(format_chats([]), "(no chats found)")

    def test_format_chats_lists_entries(self):
        out = format_chats(
            [
                {"name": "Alice", "snippet": "hi there", "timestamp": "10:42", "unread": True},
                {"name": "Project X", "snippet": "deploy soon"},
            ]
        )
        self.assertIn("[1] Alice", out)
        self.assertIn("snippet: hi there", out)
        self.assertIn("timestamp: 10:42", out)
        self.assertIn("unread: True", out)
        self.assertIn("[2] Project X", out)

    def test_format_messages_empty(self):
        self.assertEqual(format_messages([]), "(no messages found)")

    def test_format_messages_lists_entries(self):
        out = format_messages(
            [
                {"author": "Alice", "body": "hello", "timestamp": "10:42"},
                {"author": "Bob", "body": "world", "timestamp": ""},
            ]
        )
        self.assertIn("[1] Alice - 10:42", out)
        self.assertIn("    hello", out)
        self.assertIn("[2] Bob", out)
        self.assertIn("    world", out)

    def test_format_teams_list(self):
        out = format_teams_list(
            [
                {"name": "Project X", "channels": ["General", "Random"]},
                {"name": "Solo Team", "channels": []},
            ]
        )
        self.assertIn("[1] Project X", out)
        self.assertIn("channels: General, Random", out)
        self.assertIn("[2] Solo Team", out)

    def test_format_teams_list_empty(self):
        self.assertEqual(format_teams_list([]), "(no teams found)")

    def test_format_post_result(self):
        out = format_post_result(
            {"status": "posted", "target": "Alice", "message": "hi", "url": "https://teams.microsoft.com/"}
        )
        self.assertIn("status: posted", out)
        self.assertIn("target: Alice", out)
        self.assertIn("message: hi", out)

    def test_to_json_round_trip(self):
        data = [{"name": "Alice", "unread": True}]
        rendered = to_json(data)
        self.assertEqual(json.loads(rendered), data)


if __name__ == "__main__":
    unittest.main()
