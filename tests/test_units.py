"""Tests for the unit folder shape and the arc report in units.py.

Two kinds of check live in that script and they fail differently. A unit-level
check reads one document against the course's own section contract, so its tests
build one unit and assert on what the checker says about it. An arc-level check
only exists because a course can be made of units that are each individually
fine, so its tests build several correct units and then break the relationship
between them.
"""

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
un = load("units")


FULL_UNIT = """\
# Unit {n}: {title}

## Introduction

{intro}

## Before You Start

By the end of this unit you can:

{objectives}

## Notes

### The starting problem

Run this a few times and watch the total drift.

```js
const total = 0;
```

### Extending the example

The same code, with the fix.

```js
const total = 1;
```

### Naming the pattern

This is **the pattern**, and it is not the coordination problem from Unit 1.

## Exercise

**Task:** extend the second code block.
**Starting point:** the second code block above.
**You'll know it works when:** the total prints 1 every time.

## Looking Ahead

{ahead}
"""

DEFAULT_OBJECTIVES = ["Trace a request", "Debug a failing x call"]


def full_unit(n=2, title="X", objectives=DEFAULT_OBJECTIVES,
              intro="Unit 1 did this, and this unit carries it on.",
              ahead="Unit 3 is next, and it keeps the same thread."):
    return FULL_UNIT.format(n=n, title=title, intro=intro, ahead=ahead,
                            objectives="\n".join(f"- {o}" for o in objectives))


class UnitsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "326"
        self.root.mkdir()
        self._home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.tmp / "home")
        ci.REGISTRY_DIR = self.tmp / "home" / ".config" / "claude-courses"
        ci.REGISTRY = ci.REGISTRY_DIR / "registry.json"
        ci.init(self.root, course_name="COMPSCI 326", term="Fall 2026")

    def tearDown(self):
        if self._home:
            os.environ["HOME"] = self._home
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- helpers

    def write_unit(self, number, title, objective="Trace a request",
                   intro=None, ahead=None, act=None, prereqs=(), body=None,
                   objectives=None, **meta_extra):
        objectives = objectives or [objective, f"Debug a failing {title.lower()} call"]
        folder, _ = un.new_unit(self.root, number, title, act=act,
                                objectives=objectives, prereqs=prereqs)
        meta = json.loads((folder / "unit.json").read_text())
        meta.update(meta_extra)
        (folder / "unit.json").write_text(json.dumps(meta, indent=2))
        text = body if body is not None else FULL_UNIT.format(
            n=number, title=title,
            objectives="\n".join(f"- {o}" for o in objectives),
            intro=intro if intro is not None
            else f"Unit {number - 1} set this up, and this unit carries it on.",
            ahead=ahead if ahead is not None
            else f"Unit {number + 1} takes the same idea further.")
        (folder / "unit.md").write_text(text)
        return folder

    def check(self, number):
        unit = un.find_unit(self.root, number)
        return un.check_unit(self.root, unit)

    def ids(self, findings):
        return [f["id"] for f in findings]

    def arc_ids(self):
        return [f["id"] for f in un.arc_report(self.root)["findings"]]


# ------------------------------------------------------------------ the shape

class TestShapeConfig(UnitsCase):
    def test_default_preset_when_nothing_configured(self):
        cfg = un.units_config(self.root)
        headings = [s["heading"] for s in cfg["sections"]]
        self.assertEqual(headings[0], "Introduction")
        self.assertIn("Looking Ahead", headings)

    def test_preset_is_written_into_course_json_and_editable(self):
        cfg = un.units_config(self.root)
        cfg["sections"] = [{"heading": "Overview", "required": True},
                           {"heading": "Wrap Up", "required": True}]
        un.save_units_config(self.root, cfg)
        again = un.units_config(self.root)
        self.assertEqual([s["heading"] for s in again["sections"]],
                         ["Overview", "Wrap Up"])

    def test_a_course_can_use_a_shape_this_script_never_heard_of(self):
        """The whole point of the config: the contract is the course's, not this
        script's. A unit matching the custom shape passes; the preset does not."""
        cfg = un.units_config(self.root)
        cfg["sections"] = [{"heading": "Claim", "required": True},
                           {"heading": "Proof", "required": True}]
        cfg["objectives"] = {"min": 0, "max": 9}
        un.save_units_config(self.root, cfg)
        self.write_unit(1, "Induction",
                        body="# Unit 1: Induction\n\n## Claim\n\nEvery n.\n\n"
                             "## Proof\n\nBase case, then the step.\n")
        self.assertNotIn("missing-section", self.ids(self.check(1)))

    def test_units_folder_follows_the_course_naming_style(self):
        ci.ensure_layout(self.root, naming="title")
        self.assertEqual(un.units_dir(self.root), self.root / "Course" / "Units")


class TestNewUnit(UnitsCase):
    def test_creates_folder_metadata_and_skeleton(self):
        folder, created = un.new_unit(self.root, 3, "Retries and backoff",
                                      objectives=["Implement a retry budget"])
        self.assertEqual(folder.name, "03-retries-and-backoff")
        meta = json.loads((folder / "unit.json").read_text())
        self.assertEqual(meta["number"], 3)
        self.assertEqual(meta["status"], "draft")
        self.assertIn("## Looking Ahead", (folder / "unit.md").read_text())
        self.assertTrue(any("code" in c for c in created))

    def test_objectives_are_written_where_the_student_sees_them(self):
        folder, _ = un.new_unit(self.root, 1, "Sockets",
                                objectives=["Trace a request through a server"])
        self.assertIn("Trace a request through a server",
                      (folder / "unit.md").read_text())

    def test_refuses_a_duplicate_number(self):
        un.new_unit(self.root, 1, "First")
        with self.assertRaises(SystemExit):
            un.new_unit(self.root, 1, "Also first")

    def test_links_the_previous_unit_forward(self):
        first, _ = un.new_unit(self.root, 1, "First")
        un.new_unit(self.root, 2, "Second")
        self.assertEqual(json.loads((first / "unit.json").read_text())["next"], 2)

    def test_does_not_overwrite_an_existing_next(self):
        first, _ = un.new_unit(self.root, 1, "First")
        meta = json.loads((first / "unit.json").read_text())
        meta["next"] = 9
        (first / "unit.json").write_text(json.dumps(meta))
        un.new_unit(self.root, 2, "Second")
        self.assertEqual(json.loads((first / "unit.json").read_text())["next"], 9)


# -------------------------------------------------------------- reading files

class TestParsing(UnitsCase):
    def test_heading_normalization(self):
        for raw in ("### The Starting Problem", "### 1. the starting problem:",
                    "### **The starting problem**"):
            self.assertEqual(un.normalize_heading(raw.lstrip("# ")),
                             "the starting problem", raw)

    def test_a_comment_inside_a_code_block_is_not_a_section(self):
        text = "# Unit 1: Shell\n\n## Notes\n\n```bash\n# Introduction\necho hi\n```\n"
        _, sections = un.parse_sections(text)
        self.assertEqual([s["key"] for s in sections], ["notes"])

    def test_unlabeled_fence_is_reported_labeled_one_is_not(self):
        text = "```js\nlet a;\n```\n\n```\nplain\n```\n"
        self.assertEqual([lang for _, lang in un.code_fences(text)], ["js", ""])


# ------------------------------------------------------------- one unit alone

class TestCheckUnit(UnitsCase):
    def test_a_complete_unit_is_clean(self):
        self.write_unit(2, "Idempotency", objective="Implement an idempotency key")
        self.assertEqual(self.check(2), [])

    def test_missing_required_section_fails(self):
        self.write_unit(1, "Sockets",
                        body="# Unit 1: Sockets\n\n## Introduction\n\nHello there.\n")
        found = [f for f in self.check(1) if f["id"] == "missing-section"]
        self.assertTrue(found)
        self.assertEqual(found[0]["level"], un.FAIL)

    def test_sections_out_of_order(self):
        self.write_unit(1, "Sockets",
                        body="# Unit 1: Sockets\n\n## Looking Ahead\n\nUnit 2 next.\n\n"
                             "## Introduction\n\nA thing.\n\n## Before You Start\n\nRead it.\n\n"
                             "## Notes\n\nStuff.\n\n## Exercise\n\nDo it.\n")
        self.assertIn("section-order", self.ids(self.check(1)))

    def test_missing_notes_beat(self):
        text = full_unit()
        self.write_unit(2, "X", objectives=DEFAULT_OBJECTIVES,
                        body=text.replace("### Naming the pattern",
                                          "### Some other heading"))
        self.assertIn("missing-beat", self.ids(self.check(2)))

    def test_beats_out_of_order(self):
        swapped = full_unit().replace("### The starting problem", "### TEMP")
        swapped = swapped.replace("### Extending the example", "### The starting problem")
        swapped = swapped.replace("### TEMP", "### Extending the example")
        self.write_unit(2, "X", objectives=DEFAULT_OBJECTIVES, body=swapped)
        self.assertIn("beat-order", self.ids(self.check(2)))

    def test_missing_labeled_exercise_line(self):
        self.write_unit(2, "X", objectives=DEFAULT_OBJECTIVES,
                        body=full_unit().replace("**Starting point:**", "Start from"))
        self.assertIn("missing-field-line", self.ids(self.check(2)))

    def test_unlabeled_code_block(self):
        self.write_unit(2, "X", objectives=DEFAULT_OBJECTIVES,
                        body=full_unit().replace("```js", "```", 1))
        self.assertIn("unlabeled-code", self.ids(self.check(2)))

    def test_title_heading_must_match_the_metadata(self):
        self.write_unit(2, "Idempotency", objectives=DEFAULT_OBJECTIVES,
                        body=full_unit().replace("# Unit 2: X",
                                                 "# Something else entirely"))
        self.assertIn("title-mismatch", self.ids(self.check(2)))

    def test_empty_required_section(self):
        un.new_unit(self.root, 1, "Skeleton", objectives=["Trace a request"])
        self.assertIn("empty-section", self.ids(self.check(1)))

    def test_a_unit_with_no_metadata_fails(self):
        d = un.units_dir(self.root) / "07-orphan"
        d.mkdir(parents=True)
        (d / "unit.md").write_text("# Unit 7\n")
        self.assertIn("no-unit-json", self.ids(self.check(7)))

    def test_corrupt_metadata_is_reported_once_and_stops_there(self):
        folder, _ = un.new_unit(self.root, 1, "Broken")
        (folder / "unit.json").write_text("{not json")
        found = self.check(1)
        self.assertEqual(self.ids(found), ["unit-json-corrupt"])


class TestObjectives(UnitsCase):
    def test_no_objectives(self):
        folder, _ = un.new_unit(self.root, 1, "Sockets")
        self.assertIn("no-objectives", self.ids(self.check(1)))

    def test_unobservable_verb(self):
        self.write_unit(1, "Sockets", objective="Understand how sockets work")
        self.assertIn("unobservable-objective", self.ids(self.check(1)))

    def test_observable_verb_passes(self):
        self.write_unit(1, "Sockets", objective="Trace a request through a server")
        self.assertNotIn("unobservable-objective", self.ids(self.check(1)))

    def test_objective_missing_from_the_lesson(self):
        self.write_unit(1, "Sockets", objectives=["Trace a request"],
                        body=full_unit(n=1, title="Sockets",
                                       objectives=["something else entirely"]))
        self.assertIn("objective-not-stated", self.ids(self.check(1)))

    def test_count_limits_come_from_the_course_config(self):
        cfg = un.units_config(self.root)
        cfg["objectives"] = {"min": 1, "max": 1}
        un.save_units_config(self.root, cfg)
        folder = self.write_unit(1, "Sockets")
        meta = json.loads((folder / "unit.json").read_text())
        meta["objectives"] = ["Trace a request", "Explain a status code"]
        (folder / "unit.json").write_text(json.dumps(meta))
        self.assertIn("too-many-objectives", self.ids(self.check(1)))


# ------------------------------------------------------- the units together

class TestArc(UnitsCase):
    def test_a_coherent_sequence_is_clean(self):
        self.write_unit(1, "Sockets", act="Foundations",
                        intro="This course starts here.",
                        ahead="Unit 2 asks what happens when a call is repeated.")
        self.write_unit(2, "Idempotency", act="Foundations",
                        objective="Implement an idempotency key", prereqs=[1],
                        intro="Unit 1 established the request.",
                        ahead="Unit 3 turns to retries.")
        (un.units_dir(self.root) / "arc.md").write_text("# The arc\n")
        self.assertEqual([f for f in un.arc_report(self.root)["findings"]
                          if f["level"] != un.NOTE], [])

    def test_numbering_gap(self):
        self.write_unit(1, "One")
        self.write_unit(4, "Four")
        self.assertIn("numbering-gap", self.arc_ids())

    def test_duplicate_number(self):
        self.write_unit(1, "One")
        d = un.units_dir(self.root) / "01-one-again"
        d.mkdir()
        (d / "unit.json").write_text(json.dumps({"number": 1, "title": "One again"}))
        report = un.arc_report(self.root)
        dupes = [f for f in report["findings"] if f["id"] == "duplicate-number"]
        self.assertEqual(dupes[0]["level"], un.FAIL)

    def test_prerequisite_that_does_not_exist(self):
        self.write_unit(1, "One", prereqs=[9])
        self.assertIn("dangling-prereq", self.arc_ids())

    def test_prerequisite_that_comes_later(self):
        self.write_unit(1, "One")
        self.write_unit(2, "Two", prereqs=[1])
        folder = un.find_unit(self.root, 1)["path"]
        meta = json.loads((folder / "unit.json").read_text())
        meta["prereqs"] = [2]
        (folder / "unit.json").write_text(json.dumps(meta))
        found = [f for f in un.arc_report(self.root)["findings"]
                 if f["id"] == "forward-prereq"]
        self.assertTrue(found)
        self.assertEqual(found[0]["level"], un.FAIL)

    def test_looking_ahead_that_names_nothing(self):
        self.write_unit(1, "One", ahead="More to come.")
        self.write_unit(2, "Two", intro="Unit 1 set this up.")
        self.assertIn("loose-thread", self.arc_ids())

    def test_looking_ahead_may_name_the_next_unit_by_title(self):
        self.write_unit(1, "One", ahead="Next we take up idempotency.")
        self.write_unit(2, "Idempotency", intro="Unit 1 set this up.")
        self.assertNotIn("loose-thread", self.arc_ids())

    def test_introduction_that_ignores_the_previous_unit(self):
        self.write_unit(1, "One", ahead="Unit 2 is next.")
        self.write_unit(2, "Two", intro="Here is a brand new topic.")
        self.assertIn("orphan-opening", self.arc_ids())

    def test_first_unit_is_not_asked_to_reference_a_predecessor(self):
        self.write_unit(1, "One", intro="Welcome to the course.",
                        ahead="Unit 2 is next.")
        self.write_unit(2, "Two", intro="Unit 1 set this up.")
        self.assertNotIn("orphan-opening", self.arc_ids())

    def test_next_pointer_disagrees_with_disk(self):
        """A unit inserted between two others leaves the earlier one pointing
        past it."""
        self.write_unit(1, "One", ahead="Unit 2 is next.", next=3)
        self.write_unit(2, "Two", intro="Unit 1 set this up.",
                        ahead="Unit 3 is next.")
        self.write_unit(3, "Three", intro="Unit 2 set this up.")
        self.assertIn("next-mismatch", self.arc_ids())

    def test_next_pointing_at_a_unit_that_was_removed(self):
        """The pointer outlives the unit it pointed at, which is what makes a
        deleted or renumbered unit invisible until a student hits the gap."""
        self.write_unit(1, "One", ahead="Unit 2 is next.", next=2)
        self.assertIn("dangling-next", self.arc_ids())

    def test_a_unit_belonging_to_no_act(self):
        self.write_unit(1, "One", act="Foundations", ahead="Unit 2 is next.")
        self.write_unit(2, "Two", intro="Unit 1 set this up.")
        self.assertIn("units-outside-the-arc", self.arc_ids())

    def test_an_act_that_is_not_a_run_of_units(self):
        self.write_unit(1, "One", act="Foundations", ahead="Unit 2 is next.")
        self.write_unit(2, "Two", act="Middle", intro="Unit 1 set this up.",
                        ahead="Unit 3 is next.")
        self.write_unit(3, "Three", act="Foundations", intro="Unit 2 set this up.")
        self.assertIn("act-not-contiguous", self.arc_ids())

    def test_an_act_the_course_never_declared(self):
        cfg = un.units_config(self.root)
        cfg["acts"] = [{"name": "Foundations", "question": "What is a request?"}]
        un.save_units_config(self.root, cfg)
        self.write_unit(1, "One", act="Foundatons", ahead="Unit 2 is next.")
        ids = self.arc_ids()
        self.assertIn("undeclared-act", ids)
        self.assertIn("empty-act", ids)

    def test_the_same_objective_in_two_units(self):
        self.write_unit(1, "One", objective="Trace a request", ahead="Unit 2 is next.")
        self.write_unit(2, "Two", objective="Trace a request",
                        intro="Unit 1 set this up.")
        self.assertIn("repeated-objective", self.arc_ids())

    def test_no_units_at_all_is_a_note_not_a_failure(self):
        report = un.arc_report(self.root)
        self.assertEqual(self.ids(report["findings"]), ["no-units"])
        self.assertEqual(report["findings"][0]["level"], un.NOTE)

    def ids(self, findings):
        return [f["id"] for f in findings]


# ---------------------------------------------- a course that already exists

class ExistingRepoCase(unittest.TestCase):
    """A plain folder of units, with its own paths and filenames and no .infra.
    This is what a course that has been taught before actually looks like."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "426"
        self.base = self.root / "Reference Units"
        self.base.mkdir(parents=True)
        self._home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.tmp / "home")
        ci.REGISTRY_DIR = self.tmp / "home" / ".config" / "claude-courses"
        ci.REGISTRY = ci.REGISTRY_DIR / "registry.json"

    def tearDown(self):
        if self._home:
            os.environ["HOME"] = self._home
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add(self, number, slug, title, extra=(), body=None):
        d = self.base / f"{number:02d}-{slug}"
        d.mkdir()
        (d / f"{number:02d}.md").write_text(
            body if body is not None else full_unit(n=number, title=title))
        for name in extra:
            (d / name).write_text("{}")
        return d


class TestAdopt(ExistingRepoCase):
    def test_detects_the_lesson_pattern_and_the_artifacts(self):
        self.add(8, "adapter", "Adapter", extra=["08-quiz.json", "08.html"])
        self.add(9, "replicas", "Replicas", extra=["09-quiz.json"])
        found = un.detect_layout(self.base)
        self.assertEqual(found["lesson"], "{n}.md")
        self.assertIn("{n}-quiz.json", found["artifacts"])

    def test_one_folder_full_of_extras_does_not_set_the_convention(self):
        """A setup folder holding several documents must not make its first
        file alphabetically the lesson name for the whole course."""
        setup = self.base / "00-setup"
        setup.mkdir()
        for name in ("book.md", "devenv.md", "welcome.md"):
            (setup / name).write_text("# Setup\n")
        self.add(1, "concurrency", "Concurrency")
        self.add(2, "latency", "Latency")
        found = un.detect_layout(self.base)
        self.assertEqual(found["lesson"], "{n}.md")
        self.assertNotIn("book.md", found["artifacts"])

    def test_preview_writes_nothing(self):
        d = self.add(8, "adapter", "Adapter")
        before = sorted(p.name for p in d.iterdir())
        un.adopt(self.root, path="Reference Units")
        self.assertEqual(sorted(p.name for p in d.iterdir()), before)
        self.assertFalse((self.root / un.LOCAL_CONFIG).exists())

    def test_write_creates_metadata_and_a_local_config(self):
        self.add(8, "adapter", "The Adapter Pattern")
        self.add(9, "replicas", "Replicated Services")
        un.adopt(self.root, path="Reference Units", write=True)

        meta = json.loads((self.base / "08-adapter" / "unit.json").read_text())
        self.assertEqual(meta["number"], 8)
        self.assertEqual(meta["title"], "The Adapter Pattern")
        self.assertEqual(meta["next"], 9)
        self.assertEqual(meta["objectives"], [])

        cfg = json.loads((self.root / un.LOCAL_CONFIG).read_text())
        self.assertEqual(cfg["path"], "Reference Units")
        self.assertEqual(cfg["files"]["lesson"], "{n}.md")

    def test_adoption_never_overwrites_existing_metadata(self):
        d = self.add(8, "adapter", "Adapter")
        (d / "unit.json").write_text(json.dumps({"number": 8, "title": "Mine",
                                                 "objectives": ["Trace a request"]}))
        un.adopt(self.root, path="Reference Units", write=True)
        meta = json.loads((d / "unit.json").read_text())
        self.assertEqual(meta["title"], "Mine")
        self.assertEqual(meta["objectives"], ["Trace a request"])

    def test_title_strips_the_numbering_it_repeats(self):
        self.add(12, "resilience", "Resilience and Failure Modes")
        un.adopt(self.root, path="Reference Units", write=True)
        meta = json.loads((self.base / "12-resilience" / "unit.json").read_text())
        self.assertEqual(meta["title"], "Resilience and Failure Modes")


class TestAdoptedCourseChecks(ExistingRepoCase):
    """Once adopted, everything else works against the course's own filenames."""

    def adopt(self):
        un.adopt(self.root, path="Reference Units", write=True)

    def test_units_are_found_under_the_courses_own_path(self):
        self.add(8, "adapter", "Adapter")
        self.adopt()
        self.assertEqual(un.units_dir(self.root), self.base)
        self.assertEqual([u["number"] for u in un.iter_units(self.root)], [8])

    def test_check_reads_the_courses_own_lesson_filename(self):
        self.add(8, "adapter", "Adapter")
        self.adopt()
        unit = un.find_unit(self.root, 8)
        ids = [f["id"] for f in un.check_unit(self.root, unit)]
        self.assertNotIn("no-lesson", ids)
        self.assertNotIn("no-unit-json", ids)
        self.assertIn("no-objectives", ids)

    def test_a_missing_lesson_names_the_file_the_course_uses(self):
        d = self.add(8, "adapter", "Adapter")
        self.adopt()
        (d / "08.md").unlink()
        found = [f for f in un.check_unit(self.root, un.find_unit(self.root, 8))
                 if f["id"] == "no-lesson"]
        self.assertIn("08.md", found[0]["what"])

    def test_artifact_patterns_expand_per_unit(self):
        self.add(8, "adapter", "Adapter", extra=["08-quiz.json"])
        self.add(9, "replicas", "Replicas")
        self.adopt()
        cfg = un.units_config(self.root)
        present = un.artifacts_present(cfg, un.find_unit(self.root, 8))
        self.assertIn("08-quiz.json", present)
        self.assertEqual(un.artifacts_present(cfg, un.find_unit(self.root, 9)), [])

    def test_the_arc_report_runs_on_an_adopted_course(self):
        self.add(8, "adapter", "Adapter",
                 body=full_unit(n=8, title="Adapter", intro="Unit 7 set this up.",
                                ahead="Unit 9 takes it further."))
        self.add(9, "replicas", "Replicas",
                 body=full_unit(n=9, title="Replicas", intro="Unit 8 set this up.",
                                ahead="Unit 10 is next."))
        self.adopt()
        ids = [f["id"] for f in un.arc_report(self.root)["findings"]]
        self.assertNotIn("loose-thread", ids)
        self.assertNotIn("orphan-opening", ids)


if __name__ == "__main__":
    unittest.main()
