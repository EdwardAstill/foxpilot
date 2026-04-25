"""Service-layer unit tests for the youtube-music plugin."""

from __future__ import annotations

import unittest

from foxpilot.sites.youtube_music_service import (
    SECTIONS,
    YT_MUSIC_HOME,
    format_now_playing,
    format_open_result,
    format_playlist_tracks,
    format_playlists,
    format_search_results,
    is_youtube_music_url,
    normalize_kind,
    normalize_play_target,
    section_url,
    watch_url_for,
    youtube_music_search_url,
)


class UrlHelpersTests(unittest.TestCase):
    def test_section_url_returns_known_section(self):
        self.assertEqual(section_url("home"), YT_MUSIC_HOME)
        self.assertEqual(section_url("library"), SECTIONS["library"])
        self.assertEqual(section_url("playlists"), SECTIONS["playlists"])

    def test_section_url_is_case_insensitive(self):
        self.assertEqual(section_url("LIBRARY"), SECTIONS["library"])

    def test_section_url_rejects_unknown(self):
        with self.assertRaises(ValueError):
            section_url("inbox")

    def test_is_youtube_music_url_recognises_canonical_host(self):
        self.assertTrue(is_youtube_music_url("https://music.youtube.com/"))
        self.assertTrue(is_youtube_music_url("music.youtube.com/watch?v=abc"))

    def test_is_youtube_music_url_rejects_other_hosts(self):
        self.assertFalse(is_youtube_music_url("https://www.youtube.com/watch?v=abc"))
        self.assertFalse(is_youtube_music_url(""))

    def test_search_url_quotes_query(self):
        self.assertEqual(
            youtube_music_search_url("rust async"),
            "https://music.youtube.com/search?q=rust%20async",
        )

    def test_search_url_rejects_empty(self):
        with self.assertRaises(ValueError):
            youtube_music_search_url("   ")

    def test_watch_url_for_builds_canonical_watch(self):
        self.assertEqual(
            watch_url_for("abc123XYZ09"),
            "https://music.youtube.com/watch?v=abc123XYZ09",
        )


class NormalizeKindTests(unittest.TestCase):
    def test_normalize_kind_accepts_known_kinds(self):
        self.assertEqual(normalize_kind("track"), "track")
        self.assertEqual(normalize_kind("Album"), "album")
        self.assertEqual(normalize_kind("artist"), "artist")
        self.assertEqual(normalize_kind("playlist"), "playlist")

    def test_normalize_kind_aliases_song_to_track(self):
        self.assertEqual(normalize_kind("song"), "track")
        self.assertEqual(normalize_kind("songs"), "track")

    def test_normalize_kind_rejects_unknown(self):
        with self.assertRaises(ValueError):
            normalize_kind("podcast")

    def test_normalize_kind_returns_empty_for_blank(self):
        self.assertEqual(normalize_kind(""), "")


class NormalizePlayTargetTests(unittest.TestCase):
    def test_play_target_passes_through_music_url(self):
        url = "https://music.youtube.com/watch?v=abc123XYZ09"
        self.assertEqual(normalize_play_target(url), url)

    def test_play_target_extracts_video_id_from_youtube_url(self):
        self.assertEqual(
            normalize_play_target("https://www.youtube.com/watch?v=abc123XYZ09"),
            "https://music.youtube.com/watch?v=abc123XYZ09",
        )

    def test_play_target_extracts_video_id_from_shortlink(self):
        self.assertEqual(
            normalize_play_target("https://youtu.be/abc123XYZ09?t=30"),
            "https://music.youtube.com/watch?v=abc123XYZ09",
        )

    def test_play_target_falls_back_to_search(self):
        self.assertEqual(
            normalize_play_target("deftones change"),
            "https://music.youtube.com/search?q=deftones%20change",
        )

    def test_play_target_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_play_target("")


class FormattersTests(unittest.TestCase):
    def test_format_open_result_lays_out_keys(self):
        out = format_open_result(
            {"title": "YT Music", "url": YT_MUSIC_HOME, "section": "home"}
        )
        self.assertIn("title: YT Music", out)
        self.assertIn(f"url: {YT_MUSIC_HOME}", out)
        self.assertIn("section: home", out)

    def test_format_search_results_handles_empty(self):
        self.assertEqual(format_search_results([]), "No YouTube Music results found.")

    def test_format_search_results_emits_numbered_lines(self):
        out = format_search_results(
            [
                {
                    "title": "Change",
                    "url": "https://music.youtube.com/watch?v=abc",
                    "kind": "track",
                    "artist": "Deftones",
                    "album": "White Pony",
                    "duration": "5:00",
                }
            ]
        )
        self.assertIn("[1] Change", out)
        self.assertIn("kind: track", out)
        self.assertIn("artist: Deftones", out)
        self.assertIn("https://music.youtube.com/watch?v=abc", out)

    def test_format_now_playing_handles_empty(self):
        self.assertEqual(format_now_playing({}), "(nothing playing)")

    def test_format_now_playing_renders_keys(self):
        out = format_now_playing(
            {
                "title": "Change",
                "artist": "Deftones",
                "album": "White Pony",
                "position": "1:23",
                "duration": "5:00",
                "url": "https://music.youtube.com/watch?v=abc",
            }
        )
        self.assertIn("title: Change", out)
        self.assertIn("artist: Deftones", out)
        self.assertIn("position: 1:23", out)

    def test_format_playlists_handles_empty(self):
        self.assertEqual(format_playlists([]), "(no playlists found)")

    def test_format_playlists_lists_names(self):
        out = format_playlists(
            [{"name": "Daily mix 1", "url": "https://x", "track_count": 25}]
        )
        self.assertIn("Daily mix 1", out)
        self.assertIn("(25 tracks)", out)
        self.assertIn("https://x", out)

    def test_format_playlist_tracks_handles_empty(self):
        out = format_playlist_tracks({"name": "Empty PL", "tracks": []})
        self.assertIn("Empty PL", out)
        self.assertIn("(no tracks found)", out)

    def test_format_playlist_tracks_numbers_rows(self):
        out = format_playlist_tracks(
            {
                "name": "Daily mix 1",
                "tracks": [
                    {"title": "Change", "artist": "Deftones"},
                    {"title": "Digital Bath", "artist": "Deftones"},
                ],
            }
        )
        self.assertIn("Daily mix 1", out)
        self.assertIn("1. Change", out)
        self.assertIn("Deftones", out)
        self.assertIn("2. Digital Bath", out)


if __name__ == "__main__":
    unittest.main()
