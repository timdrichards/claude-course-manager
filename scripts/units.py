#!/usr/bin/env python3
"""
units.py: the on-disk shape of a course unit, and the arc the units form together.

A unit is a folder, not a file:

    course/units/09-idempotency/
    ├── unit.json      what this unit is: number, title, act, objectives, prereqs
    ├── unit.md        the lesson a student reads
    ├── code/          the examples the lesson tells them to type
    ├── quiz.json      a question bank, in the shape upload_quiz.py already takes
    ├── slides.html    the lecture deck for this unit
    └── unit.html      the Canvas render of unit.md

The folder is the boring half. The half that matters is that every unit answers
the same questions in the same places, so the course reads as one argument rather
than fifteen documents that happen to be numbered. Those questions live in
unit.json: what a student can do afterwards, which earlier units this one stands
on, and which act of the course it belongs to.

The shape is per course and recorded in .infra/course.json under "units", because
a systems course built around a broken-then-fixed code example and a theory course
built around a proof do not have the same anatomy. `shape --preset` writes a
starting point; edit it and every later check follows the edit.

Two levels of checking, and the split is deliberate:

    check   one unit against the course's own section contract
    arc     the units against each other: numbering, prerequisites, the acts,
            and whether each unit's closing promise matches what actually
            comes next

Only the second one can catch the failure that hurts students, which is fifteen
individually competent units that do not add up to anything.

Nothing here judges prose. Whether a paragraph is any good is a question for a
person and for prose_check.py; this script checks that the parts are present,
consistent with each other, and in the order the course said they would be.

Usage:
    units.py list 326
    units.py new 326 --number 9 --title "Idempotency" --act "Surviving failure"
    units.py check 326                  # every unit
    units.py check 326 9                # one unit
    units.py arc 326
    units.py shape 326 --preset knowledge-unit
    units.py path 326 9

Exit codes: 0 clean or warnings only, 1 something needs fixing, 2 bad input.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import course_infra as ci  # noqa: E402

UNIT_JSON = "unit.json"
UNIT_MD = "unit.md"
ARC_MD = "arc.md"

# A course that already has units keeps its own filenames. This is the config a
# plain repo uses, for a folder of units that is not a course-manager course.
LOCAL_CONFIG = ".units.json"

FAIL, WARN, NOTE = "FAIL", "WARN", "NOTE"


# ------------------------------------------------------------------- the shape
#
# One preset per kind of course, and the presets are starting points rather than
# a menu to choose between. The point of writing it into course.json is that the
# instructor edits it once, in one place, and every unit written afterwards is
# held to their version rather than to this file's opinion.

PRESETS = {
    # The concept-first, code-driven unit: a small example that looks fine and
    # is not, the same example repaired, then the concept named and tied back to
    # an earlier unit. The Notes beats are the load-bearing part.
    "knowledge-unit": {
        "sections": [
            {"heading": "Introduction", "required": True},
            {"heading": "Before You Start", "required": True},
            {"heading": "References", "required": False},
            {"heading": "Notes", "required": True,
             "beats": ["The starting problem", "Extending the example",
                       "Naming the pattern"]},
            {"heading": "Exercise", "required": True,
             "fields": ["Task", "Starting point", "You'll know it works when"]},
            {"heading": "Real World", "required": False},
            {"heading": "Home Exercise", "required": False},
            {"heading": "Looking Ahead", "required": True},
        ],
        "objectives": {"min": 2, "max": 5},
        "artifacts": {"code": "optional", "quiz.json": "optional",
                      "slides.html": "optional", "unit.html": "optional"},
    },
    # A lecture-shaped unit for a course whose material is not built around a
    # runnable example: the reading, the session itself, and what to practice.
    "lecture": {
        "sections": [
            {"heading": "Introduction", "required": True},
            {"heading": "Before You Start", "required": True},
            {"heading": "Notes", "required": True},
            {"heading": "Worked Example", "required": False},
            {"heading": "Practice", "required": True,
             "fields": ["Task", "You'll know it works when"]},
            {"heading": "Looking Ahead", "required": True},
        ],
        "objectives": {"min": 2, "max": 5},
        "artifacts": {"slides.html": "optional", "unit.html": "optional"},
    },
    # Almost nothing, for a course that wants the folder, the objectives, and the
    # arc without a prescribed anatomy inside the document.
    "minimal": {
        "sections": [
            {"heading": "Introduction", "required": True},
            {"heading": "Looking Ahead", "required": True},
        ],
        "objectives": {"min": 1, "max": 6},
        "artifacts": {},
    },
}

DEFAULT_PRESET = "knowledge-unit"

BASE_CONFIG = {
    "preset": DEFAULT_PRESET,
    "folder": "units",   # under course/, for a course-manager course
    "path": "",          # or an explicit folder, for a repo that already has one
    "number_width": 2,
    # Filenames, with {n} for the zero padded number and {slug} for the folder
    # slug. A course that already has units keeps whatever it already calls them.
    "files": {"meta": UNIT_JSON, "lesson": UNIT_MD},
    "acts": [],          # [{"name": ..., "question": ...}], optional
    "sections": [],
    "objectives": {"min": 2, "max": 5},
    "artifacts": {},
}

# Objectives are what a student can do, so they start with a verb someone can
# watch them do. "Understand" is not one of those, which is why it is missing.
OBJECTIVE_VERBS = {
    "explain", "describe", "identify", "implement", "build", "write", "trace",
    "compare", "contrast", "predict", "measure", "debug", "diagnose", "apply",
    "derive", "prove", "design", "evaluate", "choose", "justify", "refactor",
    "configure", "deploy", "profile", "test", "read", "modify", "extend",
    "calculate", "analyze", "analyse", "summarize", "summarise", "recognize",
    "recognise", "distinguish", "use",
}

VAGUE_OBJECTIVE_OPENERS = {"understand", "learn", "know", "appreciate",
                           "be", "become", "get", "gain", "grasp", "explore"}


def config_source(root):
    """Where this course's unit config lives.

    A course-manager course keeps it in course.json with everything else. A plain
    repo full of units, which is what most courses that already have units look
    like, gets a small file of its own rather than being made to adopt the whole
    course layout first.
    """
    if ci.infra(root).is_dir():
        return "course"
    return "local" if (root / LOCAL_CONFIG).exists() else None


def stored_config(root):
    """Only what this course actually wrote down, with no preset filled in.
    Adoption needs the difference: a preset's artifact list is a suggestion, and
    an existing course's is a fact."""
    if ci.infra(root).is_dir():
        return ci.load_course(root).get("units") or {}
    if (root / LOCAL_CONFIG).exists():
        try:
            return json.loads((root / LOCAL_CONFIG).read_text())
        except json.JSONDecodeError as e:
            sys.exit(f"{root / LOCAL_CONFIG} is not valid JSON: {e}")
    return {}


def units_config(root):
    cfg = dict(BASE_CONFIG)
    cfg.update(stored_config(root))
    cfg["files"] = {**BASE_CONFIG["files"], **(cfg.get("files") or {})}
    if not cfg.get("sections"):
        preset = PRESETS.get(cfg.get("preset") or DEFAULT_PRESET, PRESETS[DEFAULT_PRESET])
        for key, val in preset.items():
            if not cfg.get(key):
                cfg[key] = val
    return cfg


def save_units_config(root, cfg):
    if ci.infra(root).is_dir():
        course = ci.load_course(root)
        course["units"] = cfg
        ci.save_course(root, course)
        return ci.course_json_path(root)
    (root / LOCAL_CONFIG).write_text(json.dumps(cfg, indent=2) + "\n")
    return root / LOCAL_CONFIG


def units_dir(root):
    """Where units live.

    An explicit `path` wins and is used exactly as written, because a folder
    called `Reference Units` was named by a person and renaming it to suit a
    tool is the tool's problem, not theirs. Otherwise it is the course layout's
    own units folder, under the course's naming style.
    """
    cfg = units_config(root)
    if cfg.get("path"):
        return root / cfg["path"]
    style = ci.NAMING_STYLES[ci.naming_style(root)]
    return root / style(ci.COURSE_DIR) / style(cfg.get("folder") or "units")


def expand(pattern, number, width=2, slug=""):
    """`{n}` is the zero padded number, `{number}` the bare one, `{slug}` the
    folder's slug. A pattern with no placeholder is a literal filename."""
    n = f"{int(number):0{width}d}" if number is not None else ""
    return (str(pattern).replace("{n}", n)
            .replace("{number}", str(number if number is not None else ""))
            .replace("{slug}", slug))


def unit_file(cfg, unit, key):
    """The path to one of a unit's two required files, under whatever this
    course calls it."""
    pattern = (cfg.get("files") or {}).get(key) or BASE_CONFIG["files"][key]
    slug = re.sub(r"^\d+[-_]?", "", unit["name"])
    return unit["path"] / expand(pattern, unit["number"],
                                 cfg.get("number_width", 2), slug)


# -------------------------------------------------------------- reading a unit

def unit_folder_name(root, number, title, width=2):
    slug = ci.NAMING_STYLES[ci.naming_style(root)](title or "unit")
    return f"{int(number):0{width}d}-{slug}"


def load_unit(path):
    """One unit's metadata. A folder with no metadata file is still a unit, and
    saying so is more useful than pretending the folder is not there."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"_corrupt": f"{path} is not valid JSON: {e}"}


def number_from_name(name):
    m = re.match(r"(\d+)", name)
    return int(m.group(1)) if m else None


def iter_units(root, cfg=None):
    """Every unit folder, in number order. Numbered from the metadata when there
    is any, from the folder-name prefix otherwise, so a unit is placed correctly
    while it is still being written and before it has been adopted."""
    cfg = cfg or units_config(root)
    base = units_dir(root)
    if not base.is_dir():
        return []
    found = []
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        # Filenames come from the folder's own number, since that is what is on
        # disk. The number the unit reports is the metadata's when it has one.
        unit = {"path": d, "name": d.name, "number": number_from_name(d.name)}
        unit["meta_path"] = unit_file(cfg, unit, "meta")
        unit["lesson_path"] = unit_file(cfg, unit, "lesson")
        meta = load_unit(unit["meta_path"]) or {}
        if isinstance(meta.get("number"), int):
            unit["number"] = meta["number"]
        unit.update({"meta": meta, "has_meta": unit["meta_path"].exists()})
        found.append(unit)
    return sorted(found, key=lambda u: (u["number"] is None, u["number"] or 0, u["name"]))


def find_unit(root, number, cfg=None):
    for u in iter_units(root, cfg):
        if u["number"] == int(number):
            return u
    return None


# ---------------------------------------------------------- reading a document

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.M)
FENCE = re.compile(r"^([ \t]*)(`{3,}|~{3,})[ \t]*([A-Za-z0-9_+-]*)[ \t]*$", re.M)


def normalize_heading(text):
    """'### 4. The Starting Problem:' -> 'the starting problem'. Instructors
    number their headings, or do not, and it should not change the answer."""
    t = re.sub(r"^\s*\d+[.)]\s*", "", text.strip())
    t = re.sub(r"[:.\s]+$", "", t)
    t = re.sub(r"[*_`]", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def parse_sections(text):
    """Top-level (H2, or H1 after the title) sections, each with its body and
    its own subheadings. Code fences are blanked first so a '# comment' line
    inside a shell example is not read as a section."""
    masked = mask_code(text)
    heads = [{"level": len(m.group(1)), "text": m.group(2),
              "key": normalize_heading(m.group(2)),
              "start": m.start(), "line": text.count("\n", 0, m.start()) + 1}
             for m in HEADING.finditer(masked)]
    for i, h in enumerate(heads):
        h["end"] = heads[i + 1]["start"] if i + 1 < len(heads) else len(text)
        h["body"] = text[h["start"]:h["end"]]

    # Section level: the shallowest heading below the title. A document that
    # uses H1 for its sections has no such heading, so the sections are the H1s
    # after the first one, which is the title.
    top = min((h["level"] for h in heads if h["level"] > 1), default=None)
    if top is None:
        heads_after_title = [h for h in heads if h["level"] == 1][1:]
        top = 1 if heads_after_title else 2
    sections = []
    for i, h in enumerate(heads):
        if h["level"] != top:
            continue
        end = next((heads[j]["start"] for j in range(i + 1, len(heads))
                    if heads[j]["level"] <= top), len(text))
        subs = [s for s in heads[i + 1:] if s["start"] < end and s["level"] == top + 1]
        sections.append({**h, "body": text[h["start"]:end], "subs": subs})
    return heads, sections


def mask_code(text):
    """Blank fenced code, preserving offsets and line numbers."""
    out = list(text)
    fence = None
    for m in FENCE.finditer(text):
        if fence is None:
            fence = m
        elif m.group(2)[0] == fence.group(2)[0]:
            for i in range(fence.start(), min(m.end(), len(out))):
                if out[i] != "\n":
                    out[i] = " "
            fence = None
    if fence is not None:
        for i in range(fence.start(), len(out)):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def code_fences(text):
    """(line, language) for every opening fence, so a block with no language can
    be reported. Canvas renders unhighlighted code from an unlabeled fence."""
    fences, open_fence = [], None
    for m in FENCE.finditer(text):
        if open_fence is None:
            open_fence = m
            fences.append((text.count("\n", 0, m.start()) + 1, m.group(3) or ""))
        elif m.group(2)[0] == open_fence.group(2)[0]:
            open_fence = None
    return fences


def squash(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def section_is_empty(section):
    """Everything under the heading, with its own subheadings and the labeled
    field lines removed. What is left is what a student actually reads."""
    body = re.sub(r"^\s*#{1,6}\s+.*$", "", section["body"], flags=re.M)
    body = re.sub(r"^\s*\*\*[^*]{1,40}:?\*\*:?\s*$", "", body, flags=re.M)
    return len(re.findall(r"[A-Za-z0-9]+", body)) < 4


# --------------------------------------------------------------- checking one

def finding(level, ident, what, fix, unit=None, line=None):
    f = {"level": level, "id": ident, "what": what, "fix": fix}
    if unit:
        f["unit"] = unit
    if line:
        f["line"] = line
    return f


def check_unit(root, unit, cfg=None):
    """One unit against the course's own section contract."""
    cfg = cfg or units_config(root)
    name = unit["name"]
    out = []
    meta = unit["meta"] or {}

    if meta.get("_corrupt"):
        return [finding(FAIL, "unit-json-corrupt", meta["_corrupt"],
                        "Fix the JSON. Everything else about this unit is "
                        "invisible until it parses.", name)]
    if not unit["has_meta"]:
        out.append(finding(FAIL, "no-unit-json",
                           f"{name}/ has no {unit['meta_path'].name}.",
                           f"Run `units.py adopt` to write one from what is "
                           f"already in the folder, or `units.py new` for a "
                           f"unit that does not exist yet.", name))
    for key in ("number", "title"):
        if unit["has_meta"] and not meta.get(key):
            out.append(finding(FAIL, "missing-field",
                               f"{unit['meta_path'].name} has no {key}.",
                               f"Add {key}. The arc report cannot place this "
                               f"unit without it.", name))

    md = unit["lesson_path"]
    if not md.exists():
        out.append(finding(FAIL, "no-lesson", f"{name}/ has no {md.name}.",
                           "The lesson is the one required artifact.", name))
        return out + check_objectives(cfg, meta, name, None) + check_artifacts(cfg, unit)

    text = md.read_text()
    heads, sections = parse_sections(text)
    present = {s["key"]: s for s in sections}

    # Required sections, and the order they were promised in.
    order_seen = []
    for spec in cfg["sections"]:
        key = normalize_heading(spec["heading"])
        sec = present.get(key)
        if sec is None:
            if spec.get("required", False):
                out.append(finding(FAIL, "missing-section",
                                   f"no '{spec['heading']}' section.",
                                   f"Every unit in this course has one. The "
                                   f"shape is in .infra/course.json under "
                                   f"\"units\".", name))
            continue
        order_seen.append((cfg["sections"].index(spec), sec["line"], spec["heading"]))

        if spec.get("required", False) and section_is_empty(sec):
            out.append(finding(WARN, "empty-section",
                               f"'{spec['heading']}' has a heading and nothing "
                               f"under it.",
                               "Either write it or remove it. A skeleton "
                               "published with empty sections tells a student "
                               "the material is missing rather than that it is "
                               "coming.", name, sec["line"]))

    for i in range(1, len(order_seen)):
        if order_seen[i][1] < order_seen[i - 1][1]:
            out.append(finding(WARN, "section-order",
                               f"'{order_seen[i][2]}' comes before "
                               f"'{order_seen[i - 1][2]}'.",
                               "Students read units in the same order every "
                               "week and navigate by position. Match the "
                               "configured order.", name, order_seen[i][1]))
            break

    # Sections with an internal shape: beats and labeled fields.
    for spec in cfg["sections"]:
        sec = present.get(normalize_heading(spec["heading"]))
        if sec is None:
            continue
        for beat in spec.get("beats", []):
            if not any(normalize_heading(s["text"]) == normalize_heading(beat)
                       for s in sec["subs"]):
                out.append(finding(WARN, "missing-beat",
                                   f"'{spec['heading']}' has no '{beat}' "
                                   f"subsection.",
                                   "The beats are how a reader knows where they "
                                   "are inside a long section. Use the same "
                                   "heading text the other units use.",
                                   name, sec["line"]))
        if spec.get("beats"):
            want = [normalize_heading(b) for b in spec["beats"]]
            got = [normalize_heading(s["text"]) for s in sec["subs"]]
            got = [g for g in got if g in want]
            if got and got != sorted(got, key=want.index):
                out.append(finding(WARN, "beat-order",
                                   f"'{spec['heading']}' subsections are out of "
                                   f"order: {', '.join(got)}.",
                                   f"Expected order: {', '.join(want)}.",
                                   name, sec["line"]))
        for field in spec.get("fields", []):
            if not re.search(r"\*\*\s*" + re.escape(field) + r"\b", sec["body"], re.I):
                out.append(finding(WARN, "missing-field-line",
                                   f"'{spec['heading']}' has no **{field}:** line.",
                                   "The labeled lines are what make an exercise "
                                   "skimmable and unambiguous.", name, sec["line"]))

    # The first heading is what Canvas derives a page title from.
    first_h1 = next((h for h in heads if h["level"] == 1), None)
    if first_h1 is None:
        out.append(finding(WARN, "no-title-heading",
                           f"{md.name} has no top-level heading.",
                           "Start with `# Unit N: Title`. The Canvas page title "
                           "is derived from it.", name, 1))
    elif meta.get("number") is not None and meta.get("title"):
        want = squash(f"{meta['number']} {meta['title']}")
        if squash(first_h1["text"]) != want and want not in squash(first_h1["text"]):
            out.append(finding(WARN, "title-mismatch",
                               f"heading '{first_h1['text']}' does not match "
                               f"unit {meta['number']}: {meta['title']}.",
                               "The heading and unit.json name the same unit to "
                               "a student and to the tooling. Keep them equal.",
                               name, first_h1["line"]))

    for line, lang in code_fences(text):
        if not lang:
            out.append(finding(WARN, "unlabeled-code",
                               "a code block declares no language.",
                               "Fence it as ```js, ```python, and so on. The "
                               "Canvas render highlights by language and an "
                               "unlabeled block ships monochrome.", name, line))

    out += check_objectives(cfg, meta, name, text)
    out += check_artifacts(cfg, unit)
    return out


def check_objectives(cfg, meta, name, text):
    """Objectives are the spine of the arc report, so they are checked here even
    though nothing in the document requires them."""
    out = []
    objectives = meta.get("objectives") or []
    limits = cfg.get("objectives") or {}
    low, high = limits.get("min", 0), limits.get("max", 99)

    if not objectives:
        return [finding(WARN, "no-objectives",
                        "no learning objectives in unit.json.",
                        "Two to four things a student can do afterwards. This "
                        "is what the arc report tracks across the course, and "
                        "what a student uses to tell whether they got it.",
                        name)]
    if len(objectives) < low:
        out.append(finding(WARN, "too-few-objectives",
                           f"{len(objectives)} objective(s); this course "
                           f"expects at least {low}.",
                           "Add what else the unit actually delivers, or lower "
                           "the minimum in the course's units config.", name))
    if len(objectives) > high:
        out.append(finding(WARN, "too-many-objectives",
                           f"{len(objectives)} objectives; this course expects "
                           f"at most {high}.",
                           "A unit that promises seven things usually delivers "
                           "two and mentions five. Split it or cut.", name))

    for obj in objectives:
        first = re.sub(r"[^a-z]", "", str(obj).strip().split(" ")[0].lower())
        if first in VAGUE_OBJECTIVE_OPENERS:
            out.append(finding(WARN, "unobservable-objective",
                               f"objective starts with '{first}': {obj!r}",
                               "Write what the student does where you can see "
                               "it: implement, trace, compare, predict, debug. "
                               "Nobody can check whether someone understands.",
                               name))
        elif first and first not in OBJECTIVE_VERBS:
            out.append(finding(NOTE, "objective-verb",
                               f"objective does not start with a familiar "
                               f"action verb: {obj!r}",
                               "Fine if it is deliberate. Objectives read best "
                               "as a verb the student performs.", name))

        if text and squash(str(obj)) not in squash(text):
            out.append(finding(NOTE, "objective-not-stated",
                               f"objective is not written anywhere in the "
                               f"lesson: {obj!r}",
                               "Put the objectives in front of the student, "
                               "usually under Before You Start. An objective "
                               "only the tooling can see does not orient "
                               "anyone.", name))
    return out


def artifact_name(cfg, unit, pattern):
    slug = re.sub(r"^\d+[-_]?", "", unit["name"])
    return expand(pattern, unit["number"], cfg.get("number_width", 2), slug)


def check_artifacts(cfg, unit):
    out = []
    for pattern, requirement in (cfg.get("artifacts") or {}).items():
        name = artifact_name(cfg, unit, pattern)
        if requirement == "required" and not (unit["path"] / name).exists():
            out.append(finding(FAIL, "missing-artifact",
                               f"{name} is required by this course and is "
                               f"not here.",
                               f"Create {unit['name']}/{name}.", unit["name"]))
    return out


def artifacts_present(cfg, unit):
    """What this unit actually has, under whatever the course calls it. The
    fallback list is for a course that has not configured any artifacts yet."""
    patterns = list((cfg.get("artifacts") or {}).keys()) or [
        "code", "quiz.json", "slides.html", "unit.html"]
    seen = []
    for pattern in dict.fromkeys(patterns):
        name = artifact_name(cfg, unit, pattern)
        if (unit["path"] / name).exists() and name not in seen:
            seen.append(name)
    return seen


# ---------------------------------------------------------------- the sequence

def arc_report(root):
    """The units against each other. Everything here is invisible from inside a
    single unit, which is exactly why courses drift: each unit is fine."""
    cfg = units_config(root)
    units = iter_units(root)
    out = []

    if not units:
        return {"units": [], "findings": [
            finding(NOTE, "no-units", f"no units in {units_dir(root)}.",
                    "Create the first one with `units.py new`.")], "acts": {}}

    by_number = {}
    for u in units:
        if u["number"] is None:
            out.append(finding(FAIL, "unnumbered",
                               f"{u['name']}/ has no unit number.",
                               "Add a number to unit.json, or name the folder "
                               "NN-slug.", u["name"]))
            continue
        by_number.setdefault(u["number"], []).append(u)

    for num, group in sorted(by_number.items()):
        if len(group) > 1:
            out.append(finding(FAIL, "duplicate-number",
                               f"unit {num} exists twice: "
                               f"{', '.join(g['name'] for g in group)}.",
                               "Two units with one number breaks every "
                               "reference to it, including the students'."))

    numbers = sorted(by_number)
    if numbers:
        gaps = [n for n in range(numbers[0], numbers[-1]) if n not in by_number]
        if gaps:
            out.append(finding(WARN, "numbering-gap",
                               f"no unit {', '.join(str(g) for g in gaps)}, "
                               f"between {numbers[0]} and {numbers[-1]}.",
                               "A missing number reads to a student as material "
                               "they were not given. Renumber, or say in the "
                               "arc what the gap is."))

    ordered = [by_number[n][0] for n in numbers]

    # Prerequisites have to exist and have to come earlier. A course whose
    # prerequisite chain points forward is not teachable in the order it is
    # numbered, whatever the individual units say.
    for u in ordered:
        meta = u["meta"] or {}
        for pre in meta.get("prereqs") or []:
            if pre not in by_number:
                out.append(finding(FAIL, "dangling-prereq",
                                   f"names unit {pre} as a prerequisite; there "
                                   f"is no unit {pre}.",
                                   "Fix the number, or write the missing unit.",
                                   u["name"]))
            elif pre >= u["number"]:
                out.append(finding(FAIL, "forward-prereq",
                                   f"depends on unit {pre}, which comes after "
                                   f"it.",
                                   "Reorder the units, or the dependency is on "
                                   "something this unit has to teach itself.",
                                   u["name"]))

    # The thread: each unit's closing promise against what actually follows.
    for i, u in enumerate(ordered):
        meta = u["meta"] or {}
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        declared = meta.get("next")
        if declared is not None and declared not in by_number:
            out.append(finding(WARN, "dangling-next",
                               f"unit.json points at unit {declared}, which "
                               f"does not exist.",
                               "The unit it promised was renumbered or removed. "
                               "Fix the pointer, and check what Looking Ahead "
                               "still says.", u["name"]))
        elif declared is not None and nxt and declared != nxt["number"]:
            out.append(finding(WARN, "next-mismatch",
                               f"unit.json says next is {declared}; the next "
                               f"unit on disk is {nxt['number']}.",
                               "One of the two is stale.", u["name"]))
        out += thread_findings(u, ordered[i - 1] if i else None, nxt)

    out += act_findings(root, cfg, ordered)
    out += objective_findings(ordered)

    arc_file = units_dir(root) / ARC_MD
    if not arc_file.exists():
        out.append(finding(NOTE, "no-arc-document",
                           f"no {ARC_MD} in {units_dir(root)}.",
                           "One page: the question the course answers, the acts "
                           "it moves through, and what a student can do at the "
                           "end. It is what the unit sequence is for."))

    return {"units": ordered, "findings": out, "acts": group_by_act(cfg, ordered),
            "arc_document": str(arc_file) if arc_file.exists() else None}


def thread_findings(unit, prev, nxt):
    """Does this unit's Looking Ahead name what comes next, and does its opening
    name what came before? This is the cheapest possible proxy for continuity and
    it catches the real failure: a unit inserted or reordered later, leaving the
    neighbours describing a sequence that no longer exists."""
    out = []
    md = unit["lesson_path"]
    if not md.exists():
        return out
    _, sections = parse_sections(md.read_text())
    present = {s["key"]: s for s in sections}

    ahead = present.get("looking ahead")
    if ahead is not None and nxt:
        body = squash(ahead["body"])
        title = squash((nxt["meta"] or {}).get("title") or "")
        if f"unit {nxt['number']}" not in body and (not title or title not in body):
            out.append(finding(WARN, "loose-thread",
                               f"Looking Ahead does not name unit "
                               f"{nxt['number']}"
                               + (f" ({(nxt['meta'] or {}).get('title')})"
                                  if title else "") + ".",
                               "Name the next unit and the thread that carries "
                               "into it. A closing paragraph that promises "
                               "something else is how a student loses the plot.",
                               unit["name"], ahead["line"]))

    intro = present.get("introduction")
    if intro is not None and prev:
        body = squash(intro["body"])
        title = squash((prev["meta"] or {}).get("title") or "")
        if f"unit {prev['number']}" not in body and (not title or title not in body):
            out.append(finding(WARN, "orphan-opening",
                               f"the Introduction does not name unit "
                               f"{prev['number']}, the unit before it.",
                               "Say what the previous unit established and why "
                               "this one follows. That sentence is most of what "
                               "makes a sequence feel like a sequence.",
                               unit["name"], intro["line"]))
    return out


def group_by_act(cfg, ordered):
    acts = {}
    for u in ordered:
        acts.setdefault((u["meta"] or {}).get("act") or "", []).append(u["number"])
    return acts


def act_findings(root, cfg, ordered):
    """Acts are optional. Half-applied acts are not: a course where some units
    belong to a named part and others float is harder to read than one with no
    parts at all."""
    out = []
    declared = [a.get("name") for a in (cfg.get("acts") or []) if a.get("name")]
    used = group_by_act(cfg, ordered)
    unassigned = used.get("", [])
    named = {k: v for k, v in used.items() if k}

    if not named:
        if declared:
            out.append(finding(WARN, "acts-unused",
                               f"the course declares acts "
                               f"({', '.join(declared)}) and no unit names one.",
                               "Set \"act\" in each unit.json, or drop the acts "
                               "from the units config."))
        return out

    if unassigned:
        out.append(finding(WARN, "units-outside-the-arc",
                           f"unit(s) {', '.join(str(n) for n in unassigned)} "
                           f"belong to no act.",
                           "Every unit is part of the story or it is an "
                           "interruption in it. Assign an act, or say why this "
                           "one stands alone."))

    for act, members in named.items():
        if declared and act not in declared:
            out.append(finding(WARN, "undeclared-act",
                               f"unit(s) {', '.join(str(m) for m in members)} "
                               f"name act {act!r}, which the course does not "
                               f"declare.",
                               "Add it to \"acts\" in the units config, or fix "
                               "the spelling. Two spellings of one act is two "
                               "acts."))
        run = sorted(members)
        if run and run != list(range(run[0], run[0] + len(run))):
            out.append(finding(WARN, "act-not-contiguous",
                               f"act {act!r} covers units "
                               f"{', '.join(str(m) for m in run)}, which are "
                               f"not consecutive.",
                               "An act interrupted by unrelated units is not an "
                               "act. Reorder, or move the stray unit."))
    for act in declared:
        if act not in named:
            out.append(finding(NOTE, "empty-act",
                               f"act {act!r} has no units.",
                               "Either it is still to be written, or it is left "
                               "over from a previous plan."))
    return out


def objective_findings(ordered):
    """What the course as a whole claims to deliver."""
    out = []
    seen = {}
    for u in ordered:
        for obj in (u["meta"] or {}).get("objectives") or []:
            seen.setdefault(squash(str(obj)), []).append(u["number"])
    for key, where in seen.items():
        if len(where) > 1:
            out.append(finding(NOTE, "repeated-objective",
                               f"units {', '.join(str(w) for w in where)} claim "
                               f"the same objective.",
                               "Deliberate reinforcement is fine. An accident "
                               "means one of the two units is doing less than "
                               "it says."))
    return out


# --------------------------------------------------------------------- writing

def new_unit(root, number, title, act=None, objectives=(), prereqs=(),
             reading=None, summary=None):
    """Create the folder, the metadata, and a skeleton built from this course's
    own section list. Never overwrites."""
    cfg = units_config(root)
    base = units_dir(root)
    base.mkdir(parents=True, exist_ok=True)

    existing = find_unit(root, number)
    if existing:
        sys.exit(f"Unit {number} already exists at {existing['path']}. "
                 f"Edit it, or pick another number.")

    folder = base / unit_folder_name(root, number, title, cfg.get("number_width", 2))
    folder.mkdir(parents=True, exist_ok=True)
    created = [str(folder) + "/"]
    here = {"path": folder, "name": folder.name, "number": int(number)}

    meta = {
        "number": int(number),
        "title": title,
        "act": act or "",
        "summary": summary or "",
        "objectives": list(objectives),
        "prereqs": sorted(int(p) for p in prereqs),
        "next": None,
        "reading": reading or "",
        "status": "draft",
        "canvas": {"page_url": "", "page_id": None},
    }
    meta_path = unit_file(cfg, here, "meta")
    if not meta_path.exists():
        write_meta(meta_path, meta)
        created.append(str(meta_path))

    md_path = unit_file(cfg, here, "lesson")
    if not md_path.exists():
        md_path.write_text(skeleton(cfg, meta))
        created.append(str(md_path))

    for pattern in (cfg.get("artifacts") or {}):
        name = artifact_name(cfg, here, pattern)
        if "." in name:
            continue  # a file gets written when there is something to put in it
        if not (folder / name).exists():
            (folder / name).mkdir()
            created.append(str(folder / name) + "/")

    # The previous unit now has a successor, and its own metadata should say so.
    prev = find_unit(root, int(number) - 1, cfg)
    if prev and prev["meta"] and prev["meta"].get("next") in (None, ""):
        prev["meta"]["next"] = int(number)
        write_meta(prev["meta_path"], prev["meta"])
        created.append(f"{prev['name']}/{prev['meta_path'].name} (next -> {number})")

    return folder, created


def write_meta(path, meta):
    path.write_text(json.dumps(meta, indent=2) + "\n")


# ------------------------------------------------------------------- adopting
#
# Most courses that have units already have them somewhere, under names somebody
# chose, with a folder structure that works. Adoption reads what is there and
# writes down what it found. It renames nothing and moves nothing, because a
# course is somebody's teaching and the last three years of muscle memory around
# its paths are real.

def detect_layout(base):
    """Infer the lesson filename pattern and the artifacts from a folder of
    units that already exists."""
    folders = [d for d in sorted(base.iterdir())
               if d.is_dir() and not d.name.startswith(".")
               and number_from_name(d.name) is not None]
    width = max([len(re.match(r"\d+", d.name).group(0)) for d in folders] or [2])

    # Generalize each filename by replacing this unit's own number with {n}, so
    # 12.md and 08.md are recognized as one pattern rather than eleven.
    contents, lessons = {}, {}
    for d in folders:
        padded = f"{number_from_name(d.name):0{width}d}"
        names = []
        for f in sorted(d.iterdir()):
            if f.name.startswith("."):
                continue
            generic = f.name.replace(padded, "{n}", 1) if padded in f.name else f.name
            names.append(generic)
            if f.suffix == ".md":
                lessons[generic] = lessons.get(generic, 0) + 1
        contents[d.name] = names

    # The lesson is whichever Markdown name most units share. A folder holding
    # several .md files, which is usually a setup or resources folder, must not
    # decide the convention for the rest of the course by being first.
    def rank(name):
        return (lessons[name], name in ("{n}.md", UNIT_MD), name.startswith("{n}"))

    lesson = max(lessons, key=rank) if lessons else UNIT_MD

    # A convention is something more than one unit does. A single folder's own
    # extra files, which is what a setup or resources unit is full of, are that
    # unit's business rather than the course's shape.
    seen = {}
    for names in contents.values():
        for name in set(names):
            seen[name] = seen.get(name, 0) + 1
    artifacts = {name: "optional" for name, count in seen.items()
                 if name != lesson
                 and (count > 1 or "{n}" in name or len(contents) < 2)}
    return {"folders": folders, "lesson": lesson,
            "artifacts": artifacts, "number_width": width}


def title_from_lesson(path, number):
    """The unit's own first heading, minus the numbering it repeats."""
    if not path.exists():
        return ""
    heads, _ = parse_sections(path.read_text())
    first = next((h for h in heads if h["level"] == 1), None)
    if not first:
        return ""
    text = first["text"].strip()
    return re.sub(rf"^\s*(unit\s*)?0*{number}\s*[:.\-]\s*", "", text, flags=re.I).strip()


def adopt(root, path=None, write=False):
    """Write metadata for units that already exist, from what is in the folder."""
    cfg = units_config(root)
    if path:
        cfg["path"] = path
    base = root / cfg["path"] if cfg.get("path") else units_dir(root)
    if not base.is_dir():
        sys.exit(f"No folder at {base}. Pass --path with the folder the units "
                 f"are already in.")

    found = detect_layout(base)
    if not found["folders"]:
        sys.exit(f"No numbered unit folders in {base}. Units are folders named "
                 f"NN-slug; pass --path if they live somewhere else.")
    cfg["files"] = {**cfg.get("files", {}), "lesson": found["lesson"]}
    cfg["number_width"] = found["number_width"]
    # What is on disk replaces the preset's suggestions. Anything the course
    # wrote down itself survives, since that was a decision rather than a guess.
    cfg["artifacts"] = {**found["artifacts"],
                        **(stored_config(root).get("artifacts") or {})}
    cfg["artifacts"].pop(cfg["files"]["meta"], None)

    plan, numbers = [], []
    for d in found["folders"]:
        num = number_from_name(d.name)
        numbers.append(num)
        unit = {"path": d, "name": d.name, "number": num}
        meta_path = unit_file(cfg, unit, "meta")
        if meta_path.exists():
            plan.append((meta_path, None, "already has metadata"))
            continue
        title = title_from_lesson(unit_file(cfg, unit, "lesson"), num)
        plan.append((meta_path, {
            "number": num,
            "title": title,
            "act": "",
            "summary": "",
            "objectives": [],
            "prereqs": [],
            "next": None,
            "reading": "",
            "status": "draft",
            "canvas": {"page_url": "", "page_id": None},
        }, f"from {unit_file(cfg, unit, 'lesson').name}"))

    for i, (meta_path, meta, _) in enumerate(plan):
        if meta and i + 1 < len(numbers):
            meta["next"] = numbers[i + 1]

    if write:
        for meta_path, meta, _ in plan:
            if meta:
                write_meta(meta_path, meta)
        cfg_path = save_units_config(root, cfg)
    else:
        cfg_path = None
    return {"base": base, "config": cfg, "config_path": cfg_path, "plan": plan}


def format_adoption(report, write):
    base = report["base"]
    cfg = report["config"]
    lines = [f"{'Adopted' if write else 'Would adopt'} the units in {base}", "",
             f"  lesson files:   {cfg['files']['lesson']}",
             f"  metadata files: {cfg['files']['meta']}",
             f"  artifacts:      {', '.join(cfg.get('artifacts') or {}) or 'none found'}",
             ""]
    for meta_path, meta, why in report["plan"]:
        label = meta_path.parent.name
        if meta is None:
            lines.append(f"  {label:<28} {why}")
        else:
            lines.append(f"  {label:<28} {meta_path.name}: "
                         f"unit {meta['number']}, {meta['title'] or '(no title found)'}")
    lines.append("")
    if write:
        lines.append(f"  config written to {report['config_path']}")
        lines.append("  Objectives are empty on every unit. Filling them in is the "
                     "next step, and\n  the one that makes the arc report worth "
                     "anything.")
    else:
        lines.append("  Nothing written. Re-run with --write to create these files.")
    return "\n".join(lines)


def skeleton(cfg, meta):
    """A skeleton with the course's sections and nothing invented in them. The
    prompts are HTML comments, so a half-finished unit renders as an empty
    section rather than as instructions to the student."""
    lines = [f"# Unit {meta['number']}: {meta['title']}", ""]
    for spec in cfg["sections"]:
        lines.append(f"## {spec['heading']}")
        lines.append("")
        if normalize_heading(spec["heading"]) == "before you start" and meta["objectives"]:
            lines.append("By the end of this unit you can:")
            lines.append("")
            lines += [f"- {o}" for o in meta["objectives"]]
            lines.append("")
        if meta.get("reading") and normalize_heading(spec["heading"]) == "before you start":
            lines.append(f"- Read {meta['reading']}")
            lines.append("")
        for beat in spec.get("beats", []):
            lines += [f"### {beat}", ""]
        for field in spec.get("fields", []):
            lines.append(f"**{field}:**")
        if spec.get("fields"):
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# -------------------------------------------------------------------- printing

RANK = {FAIL: 0, WARN: 1, NOTE: 2}


def print_findings(findings, quiet=False):
    shown = [f for f in findings if not (quiet and f["level"] == NOTE)]
    for f in sorted(shown, key=lambda f: (RANK[f["level"]], f.get("unit") or "")):
        where = f.get("unit") or ""
        if f.get("line"):
            where += f":{f['line']}"
        print(f"  {f['level']:<4} {where + '  ' if where else ''}{f['what']}")
        print(f"       {f['fix']}")
    return shown


def format_list(root):
    cfg = units_config(root)
    units = iter_units(root)
    if not units:
        return f"No units in {units_dir(root)} yet."
    lines = [f"Units in {units_dir(root)}", ""]
    for u in units:
        meta = u["meta"] or {}
        num = f"{u['number']:>3}" if u["number"] is not None else "  ?"
        title = meta.get("title") or u["name"]
        lines.append(f"  {num}  {title}")
        bits = []
        if meta.get("act"):
            bits.append(f"act: {meta['act']}")
        bits.append(f"{len(meta.get('objectives') or [])} objective(s)")
        if meta.get("prereqs"):
            bits.append("after " + ", ".join(str(p) for p in meta["prereqs"]))
        bits.append(meta.get("status") or "draft")
        lines.append(f"       {'  |  '.join(bits)}")
        have = artifacts_present(cfg, u)
        lines.append(f"       {', '.join(have) if have else 'no artifacts yet'}")
    return "\n".join(lines)


def format_arc(root, report):
    lines = [f"Arc for {units_dir(root)}", ""]
    acts = report["acts"]
    if any(k for k in acts):
        for act, members in acts.items():
            label = act or "(no act)"
            lines.append(f"  {label}")
            for n in members:
                u = next((x for x in report["units"] if x["number"] == n), None)
                title = (u["meta"] or {}).get("title") if u else ""
                lines.append(f"      {n:>3}  {title}")
        lines.append("")
    else:
        for u in report["units"]:
            meta = u["meta"] or {}
            lines.append(f"  {u['number']:>3}  {meta.get('title') or u['name']}")
        lines.append("")
    if report.get("arc_document"):
        lines.append(f"  arc document: {report['arc_document']}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------- the CLI

def main():
    ap = argparse.ArgumentParser(description="Course units: the folder, the "
                                             "shape, and the arc they form.")
    ap.add_argument("command",
                    choices=["list", "new", "adopt", "check", "arc", "shape", "path"])
    ap.add_argument("course", nargs="?", help="Course name or folder")
    ap.add_argument("unit", nargs="?", help="Unit number, for check and path")
    ap.add_argument("--number", type=int, help="new: the unit number")
    ap.add_argument("--title", help="new: the unit title")
    ap.add_argument("--act", help="new: which act of the course this belongs to")
    ap.add_argument("--summary", help="new: one sentence on what it delivers")
    ap.add_argument("--objective", action="append", default=[], metavar="TEXT",
                    help="new: a learning objective; repeatable")
    ap.add_argument("--prereq", action="append", default=[], type=int, metavar="N",
                    help="new: a unit this one depends on; repeatable")
    ap.add_argument("--reading", help="new: the source reading for this unit")
    ap.add_argument("--preset", choices=sorted(PRESETS),
                    help="shape: write this preset into the course config")
    ap.add_argument("--path", metavar="FOLDER",
                    help="adopt, shape: the folder the units are already in, "
                         "relative to the course root")
    ap.add_argument("--write", action="store_true",
                    help="adopt: actually write the files, rather than preview")
    ap.add_argument("--quiet", action="store_true", help="findings only, no notes")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    root = ci.resolve(args.course, allow_missing=False)
    cfg = units_config(root)

    if args.command == "shape":
        if args.preset or args.path:
            new_cfg = dict(cfg)
            if args.preset:
                new_cfg["preset"] = args.preset
                for key, val in PRESETS[args.preset].items():
                    new_cfg[key] = val
            if args.path:
                new_cfg["path"] = args.path
            written = save_units_config(root, new_cfg)
            cfg = new_cfg
            print(f"Unit shape for {root.name} written to {written}.")
            print("Edit that file to fit the course; every check follows it.\n")
        print(json.dumps(cfg, indent=2))
        return 0

    if args.command == "adopt":
        report = adopt(root, path=args.path, write=args.write)
        if args.json:
            print(json.dumps({
                "base": str(report["base"]), "config": report["config"],
                "units": [{"meta": str(m), "wrote": bool(d), "note": w}
                          for m, d, w in report["plan"]]}, indent=2))
        else:
            print(format_adoption(report, args.write))
        return 0

    if args.unit is not None and args.command in ("path", "check"):
        if not str(args.unit).lstrip("-").isdigit():
            sys.exit(f"{args.unit!r} is not a unit number. Pass the number, or "
                     f"leave it off to cover every unit.")

    if args.command == "path":
        if not args.unit:
            print(units_dir(root))
            return 0
        u = find_unit(root, args.unit)
        if not u:
            sys.exit(f"No unit {args.unit} in {units_dir(root)}.")
        print(u["path"])
        return 0

    if args.command == "new":
        number = args.number if args.number is not None else (
            int(args.unit) if args.unit and args.unit.isdigit() else None)
        if number is None or not args.title:
            sys.exit("new needs --number and --title.")
        folder, created = new_unit(root, number, args.title, act=args.act,
                                   objectives=args.objective, prereqs=args.prereq,
                                   reading=args.reading, summary=args.summary)
        print(f"Unit {number}: {args.title}")
        for c in created:
            print(f"  created {c}")
        print(f"\nWrite the lesson in {folder}, then run "
              f"`units.py check {args.course or root.name} {number}`.")
        return 0

    if args.command == "list":
        if args.json:
            print(json.dumps([
                {"number": u["number"], "name": u["name"], "path": str(u["path"]),
                 "artifacts": artifacts_present(cfg, u), **(u["meta"] or {})}
                for u in iter_units(root)], indent=2))
            return 0
        print(format_list(root))
        return 0

    if args.command == "check":
        units = iter_units(root)
        if args.unit:
            one = find_unit(root, args.unit)
            if not one:
                sys.exit(f"No unit {args.unit} in {units_dir(root)}.")
            units = [one]
        findings = []
        for u in units:
            findings += check_unit(root, u, cfg)
        if args.json:
            print(json.dumps({"findings": findings}, indent=2))
        else:
            scope = f"unit {args.unit}" if args.unit else f"{len(units)} unit(s)"
            print(f"Checked {scope} in {units_dir(root)}\n")
            if not print_findings(findings, args.quiet):
                print("  nothing to fix")
            print()
        return 1 if any(f["level"] == FAIL for f in findings) else 0

    if args.command == "arc":
        report = arc_report(root)
        if args.json:
            print(json.dumps({**report, "units": [
                {"number": u["number"], "name": u["name"], **(u["meta"] or {})}
                for u in report["units"]]}, indent=2))
        else:
            print(format_arc(root, report))
            if not print_findings(report["findings"], args.quiet):
                print("  the sequence is consistent")
            print()
        return 1 if any(f["level"] == FAIL for f in report["findings"]) else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
