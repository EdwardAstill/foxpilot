"""Unit tests for the Google Drive service helpers."""

from __future__ import annotations

import time
import unittest
from pathlib import Path

import pytest

from foxpilot.sites.drive_service import (
    DRIVE_VIEWS,
    build_drive_url,
    build_folder_url,
    build_search_url,
    format_download_result,
    format_items,
    format_open_result,
    format_path,
    is_drive_url,
    normalize_drive_target,
    normalize_view,
    snapshot_download_dir,
    wait_for_download,
)


class DriveViewTests(unittest.TestCase):
    def test_known_views_are_registered(self):
        self.assertEqual(
            set(DRIVE_VIEWS),
            {"home", "recent", "starred", "shared", "trash"},
        )

    def test_normalize_view_handles_aliases(self):
        self.assertEqual(normalize_view("my-drive"), "home")
        self.assertEqual(normalize_view("bin"), "trash")
        self.assertEqual(normalize_view("favorites"), "starred")
        self.assertEqual(normalize_view("shared-with-me"), "shared")
        self.assertEqual(normalize_view("home"), "home")

    def test_unknown_view_is_clear_error(self):
        with self.assertRaisesRegex(ValueError, "unknown Drive view"):
            normalize_view("archive")


class DriveUrlTests(unittest.TestCase):
    def test_build_drive_url_for_each_view(self):
        self.assertEqual(build_drive_url("home"), "https://drive.google.com/drive/my-drive")
        self.assertEqual(build_drive_url("recent"), "https://drive.google.com/drive/recent")
        self.assertEqual(build_drive_url("starred"), "https://drive.google.com/drive/starred")
        self.assertEqual(
            build_drive_url("shared"),
            "https://drive.google.com/drive/shared-with-me",
        )
        self.assertEqual(build_drive_url("trash"), "https://drive.google.com/drive/trash")

    def test_build_folder_url_quotes_id(self):
        self.assertEqual(
            build_folder_url("0ABC123"),
            "https://drive.google.com/drive/folders/0ABC123",
        )
        self.assertIn("%2F", build_folder_url("a/b"))

    def test_build_folder_url_requires_id(self):
        with self.assertRaisesRegex(ValueError, "folder id is required"):
            build_folder_url("")

    def test_build_search_url_encodes_query(self):
        self.assertEqual(
            build_search_url("budget 2026"),
            "https://drive.google.com/drive/search?q=budget%202026",
        )

    def test_build_search_url_requires_query(self):
        with self.assertRaisesRegex(ValueError, "search query is required"):
            build_search_url("")

    def test_is_drive_url_recognizes_drive_and_docs(self):
        self.assertTrue(is_drive_url("https://drive.google.com/drive/my-drive"))
        self.assertTrue(is_drive_url("https://docs.google.com/spreadsheets/d/abc/edit"))
        self.assertFalse(is_drive_url("https://example.com/"))

    def test_normalize_drive_target_passthrough_for_url(self):
        url = "https://drive.google.com/drive/folders/0ABC"
        self.assertEqual(normalize_drive_target(url), url)

    def test_normalize_drive_target_view_name_builds_url(self):
        self.assertEqual(
            normalize_drive_target("recent"),
            "https://drive.google.com/drive/recent",
        )

    def test_normalize_drive_target_rejects_non_drive_url(self):
        with self.assertRaisesRegex(ValueError, "not a Google Drive URL"):
            normalize_drive_target("https://example.com/")


class DriveFormatterTests(unittest.TestCase):
    def test_format_items_lists_visible_fields(self):
        output = format_items(
            [
                {
                    "name": "Budget.xlsx",
                    "kind": "sheet",
                    "url": "https://drive.google.com/file/d/1/view",
                    "modified": "Yesterday",
                    "size": "12 KB",
                    "owner": "me",
                },
                {
                    "name": "Projects",
                    "kind": "folder",
                    "url": "https://drive.google.com/drive/folders/abc",
                },
            ]
        )

        self.assertIn("[1] Budget.xlsx", output)
        self.assertIn("kind: sheet", output)
        self.assertIn("size: 12 KB", output)
        self.assertIn("[2] Projects", output)

    def test_format_items_empty(self):
        self.assertEqual(format_items([]), "No Drive items found.")

    def test_format_open_result(self):
        out = format_open_result(
            {
                "title": "My Drive",
                "url": "https://drive.google.com/drive/my-drive",
                "view": "home",
            }
        )
        self.assertIn("view: home", out)
        self.assertIn("title: My Drive", out)

    def test_format_path(self):
        self.assertEqual(format_path(["My Drive", "Projects"]), "My Drive / Projects")
        self.assertEqual(format_path([]), "(path unavailable)")

    def test_format_download_result(self):
        out = format_download_result(
            {
                "status": "downloaded",
                "name": "Budget.xlsx",
                "download_dir": "/tmp/downloads",
                "files": ["/tmp/downloads/Budget.xlsx"],
            }
        )
        self.assertIn("status: downloaded", out)
        self.assertIn("/tmp/downloads/Budget.xlsx", out)


class DriveDownloadTests:
    def test_snapshot_download_dir_ignores_partials(self, tmp_path: Path) -> None:
        (tmp_path / "ready.txt").write_text("done")
        (tmp_path / "incomplete.crdownload").write_text("nope")
        (tmp_path / "incomplete.part").write_text("nope")
        (tmp_path / "incomplete.tmp").write_text("nope")

        snap = snapshot_download_dir(tmp_path)

        keys = {Path(k).name for k in snap}
        assert keys == {"ready.txt"}

    def test_snapshot_download_dir_missing_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"
        assert snapshot_download_dir(missing) == {}

    def test_wait_for_download_returns_new_completed_files(self, tmp_path: Path) -> None:
        before = snapshot_download_dir(tmp_path)
        (tmp_path / "Budget.xlsx.part").write_text("partial")
        complete = tmp_path / "Budget.xlsx"
        complete.write_text("done")

        result = wait_for_download(tmp_path, before=before, timeout=0.2, poll_interval=0.01)

        assert result["status"] == "downloaded"
        assert result["files"] == [str(complete)]
        assert result["download_dir"] == str(tmp_path)

    def test_wait_for_download_detects_updated_mtime(self, tmp_path: Path) -> None:
        existing = tmp_path / "old.txt"
        existing.write_text("v1")
        before = snapshot_download_dir(tmp_path)
        time.sleep(0.05)
        existing.write_text("v2")
        # bump mtime explicitly to be safe across filesystems
        future = time.time() + 5
        import os
        os.utime(existing, (future, future))

        result = wait_for_download(tmp_path, before=before, timeout=0.2, poll_interval=0.01)
        assert result["status"] == "downloaded"
        assert str(existing) in result["files"]

    def test_wait_for_download_times_out(self, tmp_path: Path) -> None:
        before = snapshot_download_dir(tmp_path)
        with pytest.raises(TimeoutError, match="no completed download"):
            wait_for_download(tmp_path, before=before, timeout=0.02, poll_interval=0.01)


if __name__ == "__main__":
    unittest.main()
