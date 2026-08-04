"""Tests for render_html.py.

Only the parts that need no third-party packages, which is deliberate: the whole
suite runs offline with an empty environment, and `markdown`, `premailer`, and
`pygments` are the one place this plugin reaches outside the standard library.
Those imports happen inside `render()` rather than at module scope precisely so
the checks around it stay testable without them.

What is covered is what actually goes wrong: an output that Canvas would strip,
and a unit folder whose lesson is not called what this plugin calls it.
"""

import importlib.util
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


rh = load("render_html")


class TestVerify(unittest.TestCase):
    GOOD = '<html><body><h1 style="color:#000">Unit 9</h1><p>Text.</p></body></html>'

    def test_inline_styled_output_passes(self):
        self.assertEqual(rh.verify(self.GOOD), [])

    def test_a_leftover_style_block_is_caught(self):
        problems = rh.verify('<html><head><style>p{color:red}</style></head>'
                             '<body><h1>Unit 9</h1></body></html>')
        self.assertEqual(len(problems), 1)
        self.assertIn("style", problems[0])

    def test_every_tag_canvas_strips_is_named(self):
        problems = rh.verify('<h1>T</h1><link rel="x"><script>x()</script>')
        self.assertIn("link", problems[0])
        self.assertIn("script", problems[0])

    def test_a_document_with_no_heading_is_caught(self):
        """The Canvas page title is derived from the first h1 or h2, so losing
        it produces a page named something nobody chose."""
        problems = rh.verify("<html><body><p>No heading here.</p></body></html>")
        self.assertEqual(len(problems), 1)
        self.assertIn("title", problems[0])

    def test_an_h2_is_enough_to_title_a_page(self):
        self.assertEqual(rh.verify("<body><h2>Unit 9</h2></body>"), [])

    def test_the_word_style_in_prose_is_not_a_tag(self):
        self.assertEqual(rh.verify("<h1>T</h1><p>House style matters.</p>"), [])


class TestLessonInFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, *names):
        for name in names:
            (self.tmp / name).write_text("# Unit\n")

    def test_the_default_layout(self):
        self.write("unit.md")
        found, problem = rh.lesson_in(str(self.tmp))
        self.assertIsNone(problem)
        self.assertEqual(os.path.basename(found), "unit.md")

    def test_a_course_that_calls_its_lesson_something_else(self):
        self.write("12.md")
        found, problem = rh.lesson_in(str(self.tmp))
        self.assertIsNone(problem)
        self.assertEqual(os.path.basename(found), "12.md")

    def test_unit_md_wins_when_both_are_there(self):
        self.write("unit.md", "12.md")
        found, _ = rh.lesson_in(str(self.tmp))
        self.assertEqual(os.path.basename(found), "unit.md")

    def test_several_candidates_is_an_error_rather_than_a_guess(self):
        self.write("12.md", "12-notes.md")
        found, problem = rh.lesson_in(str(self.tmp))
        self.assertIsNone(found)
        self.assertIn("12-notes.md", problem)

    def test_no_markdown_at_all(self):
        self.write("quiz.json")
        found, problem = rh.lesson_in(str(self.tmp))
        self.assertIsNone(found)
        self.assertIn("no Markdown", problem)


if __name__ == "__main__":
    unittest.main()
