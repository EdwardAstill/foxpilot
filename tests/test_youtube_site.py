import unittest
from pathlib import Path

from foxpilot.sites.youtube_service import (
    extract_video_id,
    format_metadata,
    format_search_results,
    format_transcript,
    normalize_youtube_url,
    youtube_search_url,
)


class YouTubeSiteTests(unittest.TestCase):
    def test_extract_video_id_accepts_common_youtube_urls(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=abc123XYZ09"),
            "abc123XYZ09",
        )
        self.assertEqual(
            extract_video_id("https://youtu.be/abc123XYZ09?t=30"),
            "abc123XYZ09",
        )
        self.assertEqual(
            extract_video_id("https://www.youtube.com/shorts/abc123XYZ09"),
            "abc123XYZ09",
        )

    def test_normalize_youtube_url_converts_video_inputs_to_watch_url(self):
        self.assertEqual(
            normalize_youtube_url("https://youtu.be/abc123XYZ09?t=30"),
            "https://www.youtube.com/watch?v=abc123XYZ09",
        )
        self.assertEqual(
            normalize_youtube_url("https://www.youtube.com/shorts/abc123XYZ09"),
            "https://www.youtube.com/watch?v=abc123XYZ09",
        )

    def test_normalize_youtube_url_keeps_plain_queries_as_searches(self):
        self.assertEqual(normalize_youtube_url("python"), youtube_search_url("python"))
        self.assertEqual(
            normalize_youtube_url("www.youtube.com/watch?v=abc123XYZ09"),
            "https://www.youtube.com/watch?v=abc123XYZ09",
        )

    def test_youtube_search_url_encodes_query(self):
        self.assertEqual(
            youtube_search_url("rust async tutorial"),
            "https://www.youtube.com/results?search_query=rust+async+tutorial",
        )

    def test_format_search_results_is_stable_for_agents(self):
        output = format_search_results(
            [
                {
                    "title": "Rust Async Explained",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "channel": "Example Channel",
                    "duration": "18:42",
                    "views": "120K views",
                    "published": "2 years ago",
                }
            ]
        )

        self.assertIn("[1] Rust Async Explained", output)
        self.assertIn("https://www.youtube.com/watch?v=abc123", output)
        self.assertIn("channel: Example Channel", output)
        self.assertIn("duration: 18:42", output)

    def test_format_metadata_includes_known_video_fields(self):
        output = format_metadata(
            {
                "type": "video",
                "title": "Example Video",
                "url": "https://www.youtube.com/watch?v=abc123",
                "video_id": "abc123",
                "channel": "Example Channel",
                "views": "120K views",
            }
        )

        self.assertIn("title: Example Video", output)
        self.assertIn("video_id: abc123", output)
        self.assertIn("channel: Example Channel", output)

    def test_format_transcript_text_joins_segments(self):
        output = format_transcript(
            {
                "title": "Example Video",
                "url": "https://www.youtube.com/watch?v=abc123",
                "language": "en",
                "segments": [
                    {"start": 0.0, "duration": 1.2, "text": "Hello"},
                    {"start": 1.2, "duration": 1.4, "text": "world"},
                ],
                "text": "Hello\nworld",
            },
            output_format="text",
        )

        self.assertEqual(output, "Hello\nworld")

    def test_youtube_help_command_is_registered(self):
        cli_source = Path("src/foxpilot/cli.py").read_text()

        self.assertIn("youtube_app", cli_source)
        self.assertIn('name="youtube"', cli_source)

    def test_youtube_subcommand_help_is_registered(self):
        youtube_source = Path("src/foxpilot/sites/youtube.py").read_text()

        self.assertIn('@app.command(name="help")', youtube_source)
        self.assertIn('@app.command(name="search")', youtube_source)


if __name__ == "__main__":
    unittest.main()
