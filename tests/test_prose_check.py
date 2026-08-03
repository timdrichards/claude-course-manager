"""Tests for prose_check.py.

Two halves, and the second matters more. The first checks that real tells are
caught. The second checks that the things Wikipedia's guide explicitly calls
ineffective indicators are NOT caught, because a style checker that flags
hedging and transition words would make every document it touches worse.
"""

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = load("prose_check")


def ids(text, severities=None):
    out = pc.check(text)["findings"]
    if severities:
        out = [f for f in out if f["severity"] in severities]
    return {f["id"] for f in out}


class TestCharacterSet(unittest.TestCase):
    def test_em_dash_always_flagged(self):
        self.assertIn("em-dash", ids("The deadline moved — again."))

    def test_en_dash_in_range_is_fine(self):
        self.assertNotIn("em-dash", ids("Read units 8–11 this week."))

    def test_curly_quotes_flagged(self):
        self.assertIn("curly-quote", ids("He said “hello” to them."))
        self.assertIn("curly-quote", ids("That is the student’s repo."))

    def test_straight_quotes_fine(self):
        self.assertNotIn("curly-quote", ids("He said \"hello\" to the student's TA."))

    def test_assistant_residue(self):
        self.assertIn("ai-residue", ids("As an AI language model, I cannot grade."))

    def test_citation_artifact(self):
        self.assertIn("citation-artifact", ids("The score was 12 ↩ and rising."))

    def test_todo_marker_case_sensitive(self):
        self.assertIn("todo-marker", ids("TODO: finish the rubric."))
        self.assertNotIn("todo-marker", ids("I keep a todo list for grading."))


class TestStrongTells(unittest.TestCase):
    def test_negative_parallelism_variants(self):
        for s in ("It's not just a course, it's a journey.",
                  "This is not only dismissive but also harsh.",
                  "It is not about the grade, it's about the learning."):
            self.assertIn("negative-parallelism", ids(s), s)

    def test_significance_puffery(self):
        self.assertIn("significance-puffery",
                      ids("The lab stands as a testament to careful design."))
        self.assertIn("significance-puffery",
                      ids("Testing plays a crucial role in the course."))

    def test_superficial_ing_clause(self):
        self.assertIn("superficial-ing",
                      ids("We use containers, ensuring a consistent environment."))

    def test_ing_word_alone_is_fine(self):
        self.assertNotIn("superficial-ing",
                         ids("Ensuring the container runs is the first step."))

    def test_challenges_formula(self):
        self.assertIn("challenges-formula",
                      ids("Despite these challenges, the team shipped."))

    def test_summary_sentence(self):
        self.assertIn("summary-sentence", ids("In summary, the course has six units."))

    def test_vague_attribution(self):
        self.assertIn("vague-attribution", ids("Experts argue that this is best."))
        self.assertIn("vague-attribution", ids("Some critics have noted the gap."))

    def test_named_attribution_is_fine(self):
        self.assertNotIn("vague-attribution",
                         ids("Brendan Burns argues that sidecars decouple concerns."))


class TestNotTells(unittest.TestCase):
    """Wikipedia's ineffective indicators. None of these may fire."""

    STRONG = ("fix", "strong")

    def test_transition_words_do_not_fire(self):
        s = ("Furthermore, the tests passed. Moreover, coverage rose. "
             "In addition, the build is faster. However, one case remains.")
        self.assertEqual(ids(s, self.STRONG), set())

    def test_hedging_does_not_fire(self):
        s = ("This might work, and could perhaps be somewhat faster in many "
             "cases, though it generally tends to vary.")
        self.assertEqual(ids(s, self.STRONG), set())

    def test_oxford_comma_does_not_fire(self):
        s = "The flag is green, white, and gold."
        self.assertEqual(ids(s, self.STRONG), set())

    def test_formal_prose_does_not_fire(self):
        s = ("The methodology employed herein constitutes a systematic "
             "investigation of the phenomenological substrate.")
        self.assertEqual(ids(s, self.STRONG), set())

    def test_one_ai_word_is_not_a_finding(self):
        s = "Getting the deadline right is crucial for a six week term."
        self.assertNotIn("ai-vocabulary", ids(s, self.STRONG))

    def test_single_triad_does_not_fire(self):
        s = "Bring a laptop, a charger, and your student id."
        self.assertNotIn("rule-of-three", ids(s))


class TestDensity(unittest.TestCase):
    def test_vocabulary_density_escalates(self):
        s = ("This delves into the intricate tapestry of crucial and pivotal "
             "work, showcasing meticulous and vibrant delving that underscores "
             "the intricacies of an enduring landscape.")
        f = [x for x in pc.check(s)["findings"] if x["id"] == "ai-vocabulary"]
        self.assertTrue(f)
        self.assertEqual(f[0]["severity"], "strong")

    def test_repeated_triads_flagged(self):
        s = ("Bring paper, pencils, and erasers. Read slowly, carefully, and "
             "twice. Submit early, often, and completely.")
        self.assertIn("rule-of-three", ids(s))

    def test_title_case_headings(self):
        s = ("# Course Overview And Goals\n\n## Early Life And Education\n\n"
             "### Applications In Racing\n\nSome text here about things.\n")
        self.assertIn("title-case-headings", ids(s))

    def test_sentence_case_headings_fine(self):
        s = ("# Course overview\n\n## What you will build\n\n"
             "### How grading works\n\nSome text here about things.\n")
        self.assertNotIn("title-case-headings", ids(s))


class TestExemptionsAndScoping(unittest.TestCase):
    def test_code_fence_not_linted(self):
        s = "Fine prose here.\n\n```\nDespite these challenges, x = 1\n```\n"
        self.assertNotIn("challenges-formula", ids(s))

    def test_inline_code_not_linted(self):
        self.assertNotIn("summary-sentence", ids("Use `In summary, ` as a marker."))

    def test_blockquote_not_linted(self):
        s = "The guide gives this example:\n\n> In summary, it was pivotal.\n"
        self.assertEqual(ids(s, ("fix", "strong")), set())

    def test_reference_file_exempt(self):
        s = "<!-- prose-check: reference -->\n\nIn summary, experts argue it delves."
        r = pc.check(s)
        self.assertTrue(r.get("exempt"))
        self.assertEqual(r["findings"], [])

    def test_off_on_region(self):
        s = ("Good prose.\n<!-- prose-check: off -->\n"
             "In summary, experts argue.\n<!-- prose-check: on -->\n")
        self.assertEqual(ids(s, ("fix", "strong")), set())


class TestHumanSignals(unittest.TestCase):
    def test_plain_writing_registers_signals(self):
        s = ("There are four routes. It has one table. We wrote it first, and "
             "it is probably the best place to start.")
        self.assertTrue(pc.check(s)["human_signals"])

    def test_puffed_writing_has_none(self):
        s = ("The offering constitutes a comprehensive solution showcasing "
             "excellence across every dimension of the discipline.")
        self.assertEqual(pc.check(s)["human_signals"], [])


class TestSelfTest(unittest.TestCase):
    def test_bundled_self_test_passes(self):
        self.assertEqual(pc.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
