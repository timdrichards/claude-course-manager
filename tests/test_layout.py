"""Tests for the course folder layout in course_infra.py."""

import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ci = load("course_infra")


class TestNaming(unittest.TestCase):
    def test_kebab(self):
        for raw, want in [("Unit Drafts", "unit-drafts"), ("UnitDrafts", "unit-drafts"),
                          ("unit_drafts", "unit-drafts"), ("  Reference Units  ", "reference-units"),
                          ("Canvas Details!", "canvas-details")]:
            self.assertEqual(ci.to_kebab(raw), want, raw)

    def test_snake(self):
        self.assertEqual(ci.to_snake("Unit Drafts"), "unit_drafts")

    def test_title(self):
        for raw, want in [("unit-drafts", "Unit Drafts"), ("unit_drafts", "Unit Drafts"),
                          ("units", "Units")]:
            self.assertEqual(ci.to_title(raw), want, raw)

    def test_round_trip_is_stable(self):
        self.assertEqual(ci.to_kebab(ci.to_title("unit-drafts")), "unit-drafts")


class TestSemesterSlug(unittest.TestCase):
    def test_sessions_advance_the_month(self):
        self.assertEqual(ci.semester_slug("Summer Session I 2026"), "2026-06-summer-1")
        self.assertEqual(ci.semester_slug("Summer Session II 2026"), "2026-07-summer-2")

    def test_plain_terms(self):
        self.assertEqual(ci.semester_slug("Fall 2026"), "2026-09-fall")
        self.assertEqual(ci.semester_slug("Spring 2027"), "2027-01-spring")

    def test_slug_is_always_kebab(self):
        """It is a sortable identifier, not a display name."""
        for style in ci.NAMING_STYLES:
            self.assertEqual(ci.semester_slug("Fall 2026", style), "2026-09-fall", style)

    def test_slugs_sort_chronologically(self):
        terms = ["Fall 2026", "Summer Session II 2026", "Spring 2026", "Summer Session I 2026"]
        slugs = sorted(ci.semester_slug(t) for t in terms)
        self.assertEqual(slugs, ["2026-01-spring", "2026-06-summer-1",
                                 "2026-07-summer-2", "2026-09-fall"])

    def test_unparseable_term_falls_back(self):
        self.assertEqual(ci.semester_slug("Intersession Block A"), "intersession-block-a")

    def test_no_term(self):
        self.assertIsNone(ci.semester_slug(None))


class LayoutCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "326"
        self.root.mkdir()
        self._home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.tmp / "home")
        ci.REGISTRY_DIR = self.tmp / "home" / ".config" / "claude-courses"
        ci.REGISTRY = ci.REGISTRY_DIR / "registry.json"

    def tearDown(self):
        if self._home:
            os.environ["HOME"] = self._home
        shutil.rmtree(self.tmp, ignore_errors=True)

    def init(self, **kw):
        kw.setdefault("course_name", "COMPSCI 326")
        kw.setdefault("term", "Fall 2026")
        return ci.init(self.root, **kw)


class TestEnsureLayout(LayoutCase):
    def test_creates_both_levels(self):
        self.init()
        self.assertTrue((self.root / "course" / "homework").is_dir())
        self.assertTrue((self.root / "semesters" / "2026-09-fall" / "students").is_dir())

    def test_durable_and_per_term_are_separate(self):
        self.init()
        self.assertFalse((self.root / "course" / "students").exists())
        self.assertFalse((self.root / "semesters" / "2026-09-fall" / "homework").exists())

    def test_current_symlink(self):
        self.init()
        link = self.root / "semesters" / "current"
        if link.is_symlink():
            self.assertEqual(link.readlink().name, "2026-09-fall")
            self.assertTrue((link / "students").is_dir())

    def test_idempotent(self):
        self.init()
        again = ci.ensure_layout(self.root)
        self.assertEqual(again, [])

    def test_never_deletes_on_reconfigure(self):
        self.init()
        keeper = self.root / "course" / "labs" / "lab-01.md"
        keeper.write_text("real work")
        ci.ensure_layout(self.root, remove=["labs"])
        self.assertTrue(keeper.exists())
        self.assertNotIn("labs", ci.layout_config(self.root)["durable"])

    def test_add_and_skip(self):
        self.init(add_folders=["Unit Drafts", "scripts"], skip_folders=["reading"])
        self.assertTrue((self.root / "course" / "unit-drafts").is_dir())
        self.assertTrue((self.root / "course" / "scripts").is_dir())
        self.assertFalse((self.root / "course" / "reading").exists())

    def test_added_per_term_folder_lands_per_term(self):
        ci.PER_TERM_FOLDERS.setdefault("teams", "")
        self.init(add_folders=["teams"])
        self.assertTrue((self.root / "semesters" / "2026-09-fall" / "teams").is_dir())

    def test_naming_style_applied_and_persisted(self):
        self.init(naming="title")
        self.assertTrue((self.root / "Course" / "Homework").is_dir())
        self.assertEqual(ci.naming_style(self.root), "title")

    def test_bad_naming_style_rejected(self):
        with self.assertRaises(SystemExit):
            ci.ensure_layout(self.root, naming="camelCase")

    def test_no_layout_flag(self):
        ci.init(self.root, course_name="X", term="Fall 2026", layout=False)
        self.assertFalse((self.root / "course").exists())

    def test_no_term_still_builds_durable_half(self):
        ci.init(self.root, course_name="X", term=None)
        self.assertTrue((self.root / "course" / "homework").is_dir())
        self.assertFalse((self.root / "semesters").exists())


class TestGitignore(LayoutCase):
    def test_student_folders_excluded(self):
        self.init()
        gi = (self.root / ".gitignore").read_text()
        for folder in ("students", "grading", "accommodations"):
            self.assertIn(f"semesters/*/{folder}/", gi)

    def test_non_sensitive_not_excluded(self):
        self.init()
        gi = (self.root / ".gitignore").read_text()
        self.assertNotIn("announcements/", gi)
        self.assertNotIn("course/homework", gi)

    def test_existing_rules_preserved(self):
        (self.root / ".gitignore").write_text("node_modules/\n*.pyc\n")
        self.init()
        gi = (self.root / ".gitignore").read_text()
        self.assertIn("node_modules/", gi)
        self.assertIn("semesters/*/students/", gi)

    def test_not_duplicated_on_rerun(self):
        self.init()
        ci.ensure_layout(self.root)
        gi = (self.root / ".gitignore").read_text()
        self.assertEqual(gi.count("semesters/*/students/"), 1)


class TestLayoutStatus(LayoutCase):
    def test_reports_present_folders(self):
        self.init()
        s = ci.layout_status(self.root)
        self.assertTrue(s["exists"])
        self.assertIn("homework", s["durable_present"])
        self.assertIn("students", s["per_term_present"])
        self.assertEqual(s["durable_missing"], [])
        self.assertEqual(s["semester"], "2026-09-fall")

    def test_reports_missing_folder(self):
        self.init()
        shutil.rmtree(self.root / "course" / "labs")
        self.assertIn("labs", ci.layout_status(self.root)["durable_missing"])

    def test_reports_unlisted_folder(self):
        self.init()
        (self.root / "course" / "scratch").mkdir()
        self.assertIn("scratch", ci.layout_status(self.root)["unlisted"])

    def test_describe_flags_missing_layout(self):
        ci.init(self.root, course_name="X", term="Fall 2026", layout=False)
        info = ci.describe(self.root)
        self.assertTrue(any("course/" in p for p in info["problems"]))


class TestRollover(LayoutCase):
    def test_new_term_adds_a_sibling_and_moves_current(self):
        self.init()
        old = self.root / "semesters" / "2026-09-fall" / "students" / "a.md"
        old.write_text("last term")
        cfg = ci.layout_config(self.root)
        cfg["semester"] = None
        ci.save_layout_config(self.root, cfg)

        ci.ensure_layout(self.root, term="Spring 2027")
        self.assertTrue((self.root / "semesters" / "2027-01-spring" / "students").is_dir())
        self.assertTrue(old.exists(), "last term's records must survive")
        link = self.root / "semesters" / "current"
        if link.is_symlink():
            self.assertEqual(link.readlink().name, "2027-01-spring")


if __name__ == "__main__":
    unittest.main()
