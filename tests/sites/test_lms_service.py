"""Unit tests for lms_service URL helpers, validators, and formatters."""

from __future__ import annotations

import unittest

from foxpilot.sites.lms_service import (
    LMS_HOME,
    LMS_HOST,
    SECTION_PATHS,
    build_lms_url,
    course_search_url,
    format_announcements,
    format_assignments,
    format_courses,
    format_grades,
    format_open_result,
    format_stream,
    is_lms_url,
    is_sso_redirect_url,
    normalize_assignment_name,
    normalize_course_id,
    normalize_section,
)


class IsLmsUrlTests(unittest.TestCase):
    def test_accepts_canonical_lms_host(self):
        self.assertTrue(is_lms_url("https://lms.uwa.edu.au/ultra/stream"))
        self.assertTrue(is_lms_url("https://lms.uwa.edu.au/"))

    def test_accepts_subdomain_of_lms_uwa(self):
        self.assertTrue(is_lms_url("https://api.lms.uwa.edu.au/foo"))

    def test_rejects_other_hosts(self):
        self.assertFalse(is_lms_url("https://uwa.edu.au/"))
        self.assertFalse(is_lms_url("https://auth.uwa.edu.au/"))
        self.assertFalse(is_lms_url("https://example.com/"))

    def test_rejects_empty(self):
        self.assertFalse(is_lms_url(""))


class SsoDetectionTests(unittest.TestCase):
    def test_flags_pheme_auth_redirect(self):
        self.assertTrue(is_sso_redirect_url("https://auth.uwa.edu.au/idp/profile/SAML2/..."))
        self.assertTrue(is_sso_redirect_url("https://sso.uwa.edu.au/login"))

    def test_does_not_flag_lms(self):
        self.assertFalse(is_sso_redirect_url("https://lms.uwa.edu.au/ultra/stream"))


class BuildLmsUrlTests(unittest.TestCase):
    def test_default_returns_home(self):
        self.assertEqual(build_lms_url(None), LMS_HOME)
        self.assertEqual(build_lms_url(""), LMS_HOME)

    def test_each_known_section_resolves(self):
        for section, path in SECTION_PATHS.items():
            self.assertEqual(build_lms_url(section), f"https://{LMS_HOST}{path}")

    def test_section_is_case_insensitive(self):
        self.assertEqual(build_lms_url("STREAM"), build_lms_url("stream"))
        self.assertEqual(build_lms_url(" Courses "), build_lms_url("courses"))

    def test_unknown_section_raises(self):
        with self.assertRaises(ValueError):
            build_lms_url("inbox")


class NormalizeSectionTests(unittest.TestCase):
    def test_default_is_stream(self):
        self.assertEqual(normalize_section(None), "stream")
        self.assertEqual(normalize_section(""), "stream")

    def test_lowercases_and_strips(self):
        self.assertEqual(normalize_section(" Courses "), "courses")

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            normalize_section("inbox")


class CourseIdValidatorTests(unittest.TestCase):
    def test_accepts_typical_codes_and_names(self):
        self.assertEqual(normalize_course_id("GENG2000"), "GENG2000")
        self.assertEqual(
            normalize_course_id("Engineering Mathematics"),
            "Engineering Mathematics",
        )
        self.assertEqual(normalize_course_id(" GENG-2000 "), "GENG-2000")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_course_id("")
        with self.assertRaises(ValueError):
            normalize_course_id("   ")

    def test_rejects_special_characters(self):
        with self.assertRaises(ValueError):
            normalize_course_id("foo<script>")
        with self.assertRaises(ValueError):
            normalize_course_id("a/b")


class AssignmentNameValidatorTests(unittest.TestCase):
    def test_accepts_typical_assignment_names(self):
        self.assertEqual(normalize_assignment_name("Lab 3"), "Lab 3")
        self.assertEqual(
            normalize_assignment_name("Quiz 1: Intro (Week 2)"),
            "Quiz 1: Intro (Week 2)",
        )

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_assignment_name("")

    def test_rejects_disallowed_chars(self):
        with self.assertRaises(ValueError):
            normalize_assignment_name("foo<script>")


class CourseSearchUrlTests(unittest.TestCase):
    def test_encodes_query(self):
        self.assertEqual(
            course_search_url("intro to engineering"),
            f"https://{LMS_HOST}/ultra/course?query=intro+to+engineering",
        )


class FormatterTests(unittest.TestCase):
    def test_format_open_result(self):
        out = format_open_result(
            {"title": "Stream", "url": "https://lms.uwa.edu.au/ultra/stream", "section": "stream"}
        )
        self.assertIn("title: Stream", out)
        self.assertIn("url: https://lms.uwa.edu.au/ultra/stream", out)
        self.assertIn("section: stream", out)

    def test_format_stream_empty(self):
        self.assertEqual(format_stream([]), "(no stream items found)")

    def test_format_stream_includes_fields(self):
        out = format_stream(
            [
                {
                    "title": "Lab 3 due Friday",
                    "course": "GENG2000",
                    "kind": "assignment",
                    "timestamp": "2 hours ago",
                    "url": "https://lms.uwa.edu.au/x",
                }
            ]
        )
        self.assertIn("[1] Lab 3 due Friday", out)
        self.assertIn("course: GENG2000", out)
        self.assertIn("kind: assignment", out)
        self.assertIn("timestamp: 2 hours ago", out)
        self.assertIn("https://lms.uwa.edu.au/x", out)

    def test_format_courses_empty(self):
        self.assertEqual(format_courses([]), "(no courses found)")

    def test_format_courses_renders_code_title_term(self):
        out = format_courses(
            [
                {
                    "title": "Engineering Mathematics",
                    "code": "GENG2000",
                    "term": "S1 2026",
                    "url": "https://lms.uwa.edu.au/c",
                }
            ]
        )
        self.assertIn("GENG2000 Engineering Mathematics [S1 2026]", out)
        self.assertIn("https://lms.uwa.edu.au/c", out)

    def test_format_assignments(self):
        out = format_assignments(
            [{"name": "Lab 3", "course": "GENG2000", "due": "Fri", "status": "submitted"}]
        )
        self.assertIn("Lab 3", out)
        self.assertIn("course=GENG2000", out)
        self.assertIn("due=Fri", out)
        self.assertIn("status=submitted", out)

    def test_format_assignments_empty(self):
        self.assertEqual(format_assignments([]), "(no assignments found)")

    def test_format_grades(self):
        out = format_grades(
            [{"name": "Quiz 1", "score": "8/10", "weight": "5%", "posted_at": "2d"}]
        )
        self.assertIn("Quiz 1", out)
        self.assertIn("score=8/10", out)
        self.assertIn("weight=5%", out)
        self.assertIn("posted=2d", out)

    def test_format_grades_empty(self):
        self.assertEqual(format_grades([]), "(no grade items found)")

    def test_format_announcements(self):
        out = format_announcements(
            [{"title": "Welcome", "course": "GENG2000", "posted_at": "1w"}]
        )
        self.assertIn("Welcome", out)
        self.assertIn("course: GENG2000", out)
        self.assertIn("posted: 1w", out)

    def test_format_announcements_empty(self):
        self.assertEqual(format_announcements([]), "(no announcements found)")


if __name__ == "__main__":
    unittest.main()
