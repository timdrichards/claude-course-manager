#!/usr/bin/env python3
"""
Course layout: one folder per course, with tool infrastructure tucked into .infra.

    <courses root>/326/                the course
    ├── course/                        material that survives every offering:
    │                                  units, homework, labs, code, slides, videos, ...
    ├── semesters/
    │   ├── current -> 2026-07-summer-2
    │   └── 2026-07-summer-2/          material tied to one term:
    │                                  students, grading, accommodations, announcements
    └── .infra/                        everything the tooling needs, out of your way
        ├── course.json                shared identity: number, title, term, institution
        ├── course-profile.md          shared course knowledge, read by any tool
        ├── .gitignore                 keeps secrets and state out of version control
        ├── piazza/
        │   ├── config.json            class URL, assignment keywords, privatize mode
        │   ├── credentials            PIAZZA_EMAIL / PIAZZA_PASSWORD, chmod 600
        │   ├── inbox/                 fetched threads, one JSON per run
        │   ├── drafts/                replies awaiting approval
        │   ├── state/seen.json        threads already handled
        │   └── actions.log            every write, with undo information
        ├── canvas/                    same shape: config.json, credentials, inbox/, ...
        └── gradescope/

Two levels on purpose. Things that describe the *course* (what it teaches, when the
midterm is, how the instructor writes) live directly under .infra and are read by
every tool. Things that describe one *service* (a Canvas token, a Piazza password, a
Gradescope state file) live in that service's folder. A tool added later needs the
first kind and should never have to reach into another tool's folder to get it.

Courses do not all have to live in one place, and the registry is what makes that
survivable. It records where each course is, so every other script can take "326"
where it would otherwise demand a path. The registry is a convenience index, never
a source of truth: delete it and everything still works from explicit paths.

    ~/.config/claude-courses/registry.json

Usable as a CLI:

    python3 course_infra.py set-root ~/courses
    python3 course_infra.py init 326 --tool canvas --name "COMPSCI 326" --term "Fall 2026"
    python3 course_infra.py verify 326 --tool piazza
    python3 course_infra.py verify 326               # all configured tools
    python3 course_infra.py list                     # every registered course
    python3 course_infra.py layout 326                # build or repair the folder tree
    python3 course_infra.py layout 326 --term "Spring 2027"   # roll to a new term
"""

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

INFRA = ".infra"
COURSE_JSON = "course.json"
PROFILE = "course-profile.md"
CREDENTIALS = "credentials"
CONFIG = "config.json"
INBOX = "inbox"
DRAFTS = "drafts"
STATE = "state"
SEEN = "state/seen.json"
ACTIONS = "actions.log"

REGISTRY_DIR = Path.home() / ".config" / "claude-courses"
REGISTRY = REGISTRY_DIR / "registry.json"
DEFAULT_COURSES_ROOT = "~/courses"

GITIGNORE = """\
# Secrets and machine state. The profile and config are safe to commit.
*/credentials
*/state/
*/inbox/
*/actions.log
*/*.log
"""


# ---------------------------------------------------------------- the layout
#
# Two levels, and the split is the whole point: does this survive the next
# offering of the course? A homework spec does. A student's accommodation letter
# does not. Getting that boundary wrong is what makes rollover a copy-and-prune
# exercise instead of a fresh folder beside the old one.
#
# The test, from the instructor's own design notes: "would this sentence still
# be true if you taught the course again next year with different students?"

COURSE_DIR = "course"       # durable: survives every offering
SEMESTERS_DIR = "semesters"  # per-term: belongs to exactly one run of the course
CURRENT_LINK = "current"

DURABLE_FOLDERS = {
    "units": "Unit or module content, one folder per unit",
    "homework": "Assignment specs and starter code",
    "labs": "Lab material",
    "code": "Worked examples and reference implementations",
    "slides": "Decks",
    "videos": "Recordings and scripts",
    "reading": "Articles, book chapters, references",
    "drafts": "Work in progress, before it goes live",
}

PER_TERM_FOLDERS = {
    "students": "Per-student notes. Real student data.",
    "grading": "Feedback, score records, grading passes. Real student data.",
    "accommodations": "Disability Services letters. Real student data.",
    "announcements": "What was sent to this class, and when",
}

# Everything holding student records is excluded from version control by
# default. This is the on-disk half of the plugin's student-data rules, and it
# is a must rather than a suggestion: these are FERPA-protected records in the
# US and personal data under GDPR elsewhere.
SENSITIVE = {"students", "grading", "accommodations"}

COURSE_GITIGNORE_HEADER = "# Student records. Added by course_infra.py; do not commit these.\n"


# ----------------------------------------------------------- naming convention

def to_kebab(name):
    s = re.sub(r"[_\s]+", "-", str(name).strip())
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", s)
    s = re.sub(r"[^A-Za-z0-9.-]", "", s)
    return re.sub(r"-{2,}", "-", s).strip("-").lower()


def to_snake(name):
    return to_kebab(name).replace("-", "_")


def to_title(name):
    words = re.split(r"[-_\s]+", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(name).strip()))
    return " ".join(w[:1].upper() + w[1:] for w in words if w)


NAMING_STYLES = {
    "kebab": to_kebab,      # unit-drafts
    "snake": to_snake,      # unit_drafts
    "title": to_title,      # Unit Drafts
    "as-is": lambda n: str(n).strip(),
}
DEFAULT_NAMING = "kebab"


def naming_style(root):
    """Recorded per course so it is answered once and honored afterward."""
    return (load_course(root).get("layout") or {}).get("naming", DEFAULT_NAMING)


def fmt_name(root, name):
    return NAMING_STYLES[naming_style(root)](name)


MONTHS = {"spring": "01", "winter": "01", "summer": "06", "fall": "09", "autumn": "09"}


def semester_slug(term, naming=DEFAULT_NAMING):
    """'Summer Session II 2026' -> '2026-07-summer-2'.

    Always kebab, whatever the course's naming style is. This one is an
    identifier that has to sort chronologically in a directory listing, not a
    display name, and 'Semesters/2026 09 Fall' sorts and quotes badly. Unlike
    '26su' it can also express 'Session II'.
    """
    if not term:
        return None
    t = str(term).strip()
    year = (re.search(r"(20\d{2})", t) or [None, ""])[1]
    low = t.lower()
    month = next((m for k, m in MONTHS.items() if k in low), None)
    season = next((k for k in MONTHS if k in low), None)
    if not (year and season):
        return to_kebab(t)
    # Session number, from "II", "2", or "Session 2".
    roman = {"i": "1", "ii": "2", "iii": "3"}
    m = re.search(r"\b(?:session\s*)?(i{1,3}|[123])\b", low.replace(season, ""))
    part = roman.get(m.group(1), m.group(1)) if m else None
    # A later session starts a later month: Summer Session II begins in July,
    # which is what makes the slug sort correctly against Session I.
    if part and part.isdigit():
        month = f"{min(12, int(month) + int(part) - 1):02d}"
    return f"{year}-{month}-{season}" + (f"-{part}" if part else "")


# ------------------------------------------------------------ building it out

def layout_config(root):
    cfg = (load_course(root).get("layout") or {})
    return {
        "naming": cfg.get("naming", DEFAULT_NAMING),
        "durable": cfg.get("durable", sorted(DURABLE_FOLDERS)),
        "per_term": cfg.get("per_term", sorted(PER_TERM_FOLDERS)),
        "semester": cfg.get("semester"),
    }


def save_layout_config(root, cfg):
    course = load_course(root)
    course["layout"] = cfg
    save_course(root, course)


def ensure_layout(root, term=None, naming=None, add=(), remove=()):
    """Create the folder tree. Never removes anything that exists on disk:
    dropping a folder from the config stops it being created, it does not
    delete material already in it."""
    cfg = layout_config(root)
    if naming:
        if naming not in NAMING_STYLES:
            sys.exit(f"Unknown naming style {naming!r}. "
                     f"Choose from: {', '.join(NAMING_STYLES)}")
        cfg["naming"] = naming
    style = NAMING_STYLES[cfg["naming"]]

    known = set(DURABLE_FOLDERS) | set(PER_TERM_FOLDERS)
    for name in add:
        base = to_kebab(name)
        bucket = "per_term" if base in PER_TERM_FOLDERS else "durable"
        if base not in cfg[bucket]:
            cfg[bucket].append(base)
            cfg[bucket].sort()
    for name in remove:
        base = to_kebab(name)
        for bucket in ("durable", "per_term"):
            if base in cfg[bucket]:
                cfg[bucket].remove(base)

    created = []
    course_root = root / style(COURSE_DIR)
    for base in cfg["durable"]:
        d = course_root / style(base)
        if not d.exists():
            d.mkdir(parents=True)
            created.append(str(d.relative_to(root)) + "/")

    term = term or load_course(root).get("term")
    slug = cfg.get("semester") or semester_slug(term, cfg["naming"])
    if slug:
        cfg["semester"] = slug
        sem_root = root / style(SEMESTERS_DIR) / slug
        for base in cfg["per_term"]:
            d = sem_root / style(base)
            if not d.exists():
                d.mkdir(parents=True)
                created.append(str(d.relative_to(root)) + "/")

        # A stable path into the active term means nothing downstream needs
        # editing at rollover.
        link = root / style(SEMESTERS_DIR) / CURRENT_LINK
        try:
            if link.is_symlink():
                if link.readlink().name != slug:
                    link.unlink()
                    link.symlink_to(slug, target_is_directory=True)
                    created.append(f"{link.relative_to(root)} -> {slug}")
            elif not link.exists():
                link.symlink_to(slug, target_is_directory=True)
                created.append(f"{link.relative_to(root)} -> {slug}")
        except (OSError, NotImplementedError):
            pass  # filesystems without symlinks still get the real folders

    created += write_course_gitignore(root, cfg, style)
    save_layout_config(root, cfg)
    return created


def write_course_gitignore(root, cfg, style):
    """Exclude every folder holding student records. Appends rather than
    overwrites, so an instructor's own rules survive."""
    sensitive = [b for b in cfg["per_term"] if to_kebab(b) in SENSITIVE]
    if not sensitive:
        return []
    lines = [f"{style(SEMESTERS_DIR)}/*/{style(b)}/" for b in sensitive]

    gi = root / ".gitignore"
    existing = gi.read_text() if gi.exists() else ""
    missing = [l for l in dict.fromkeys(lines) if l not in existing]
    if not missing:
        return []
    body = existing
    if body and not body.endswith("\n"):
        body += "\n"
    if COURSE_GITIGNORE_HEADER not in body:
        body += "\n" + COURSE_GITIGNORE_HEADER
    body += "\n".join(missing) + "\n"
    gi.write_text(body)
    return [".gitignore (student-record folders excluded)"]


def layout_status(root):
    cfg = layout_config(root)
    style = NAMING_STYLES[cfg["naming"]]
    course_root = root / style(COURSE_DIR)
    sem_dir = root / style(SEMESTERS_DIR)
    slug = cfg.get("semester")

    present = [b for b in cfg["durable"] if (course_root / style(b)).is_dir()]
    missing = [b for b in cfg["durable"] if not (course_root / style(b)).is_dir()]
    per_present, per_missing = [], []
    if slug:
        for b in cfg["per_term"]:
            (per_present if (sem_dir / slug / style(b)).is_dir() else per_missing).append(b)

    link = sem_dir / CURRENT_LINK
    return {
        "naming": cfg["naming"], "semester": slug,
        "exists": course_root.is_dir(),
        "durable_present": present, "durable_missing": missing,
        "per_term_present": per_present, "per_term_missing": per_missing,
        "current_link": link.readlink().name if link.is_symlink() else None,
        "unlisted": sorted(
            d.name for d in course_root.iterdir()
            if course_root.is_dir() and d.is_dir()
            and d.name not in {style(b) for b in cfg["durable"]}
        ) if course_root.is_dir() else [],
    }


# ------------------------------------------------------------------ tool specs
#
# One entry per service. Adding a tool means adding a spec here and nothing else
# in this file: init, verify, and the credential loader all read from these.

TOOLS = {
    "piazza": {
        "label": "Piazza",
        "config": {
            "course_url": "",
            "assignment_keywords": [],
            "min_code_lines": 6,
            "privatize_mode": "dry-run",
        },
        "required_config": ["course_url"],
        "credentials": ["PIAZZA_EMAIL", "PIAZZA_PASSWORD"],
        "credentials_note": (
            "# Piazza login for this course. Keep this file at chmod 600.\n"
            "# If your school logs into Piazza through SSO you may have no Piazza\n"
            "# password, in which case scripted fetching will not work at all.\n"
        ),
        "identity_key": "course_url",
        "identity_pattern": r"piazza\.com/class/([a-zA-Z0-9]+)",
    },
    "canvas": {
        "label": "Canvas",
        "config": {
            "base_url": "",
            "course_id": "",
            "write_mode": "dry-run",
        },
        "required_config": ["base_url", "course_id"],
        "credentials": ["CANVAS_TOKEN"],
        "credentials_note": (
            "# Canvas API token for this course. Keep this file at chmod 600.\n"
            "# Generate one in Canvas: Account -> Settings -> New Access Token.\n"
            "# The token carries your full instructor permissions. Treat it like a\n"
            "# password, give it an expiry date, and delete it in Canvas when done.\n"
        ),
        "identity_key": "course_id",
        "identity_pattern": r"(?:instructure\.com|canvas[^\s/]*)/courses/(\d+)",
    },
    "gradescope": {
        "label": "Gradescope",
        "config": {
            "course_id": "",
            "read_only": True,
        },
        "required_config": ["course_id"],
        "credentials": ["GRADESCOPE_EMAIL", "GRADESCOPE_PASSWORD"],
        "credentials_note": (
            "# Gradescope login for this course. Keep this file at chmod 600.\n"
            "# Gradescope has no public API, so this drives the website's own login\n"
            "# form. If you sign in through your school (SSO) you probably have no\n"
            "# Gradescope password. Try 'Forgot your password?' once; if that fails,\n"
            "# log in with a browser and paste the _gradescope_session cookie below.\n"
        ),
        "identity_key": "course_id",
        "identity_pattern": r"gradescope\.com/courses/(\d+)",
    },
}

# Credential keys that are optional but recognized when present.
EXTRA_CREDENTIAL_KEYS = {"gradescope": ["GRADESCOPE_SESSION"]}


def credentials_template(tool):
    spec = TOOLS.get(tool, {})
    body = spec.get("credentials_note", f"# {tool} credentials. Keep at chmod 600.\n")
    for key in spec.get("credentials", []):
        body += f"{key}=\n"
    for key in EXTRA_CREDENTIAL_KEYS.get(tool, []):
        body += f"# Optional, instead of the password above:\n# {key}=\n"
    return body


# ------------------------------------------------------------------- registry

def load_registry():
    if not REGISTRY.exists():
        return {"courses_root": DEFAULT_COURSES_ROOT, "courses": {}}
    try:
        data = json.loads(REGISTRY.read_text())
    except json.JSONDecodeError:
        # A corrupt index should never block work that has an explicit path.
        return {"courses_root": DEFAULT_COURSES_ROOT, "courses": {}, "_corrupt": True}
    data.setdefault("courses_root", DEFAULT_COURSES_ROOT)
    data.setdefault("courses", {})
    return data


def save_registry(data):
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(data, indent=2) + "\n")


def courses_root():
    return Path(load_registry()["courses_root"]).expanduser()


def set_courses_root(path):
    reg = load_registry()
    reg.pop("_corrupt", None)
    reg["courses_root"] = str(Path(path).expanduser())
    save_registry(reg)
    return reg["courses_root"]


def register(root, key=None):
    """Record where a course lives so later commands can name it, not path to it."""
    root = Path(root).expanduser().resolve()
    course = load_course(root)
    key = key or course.get("course_number") or root.name
    reg = load_registry()
    reg.pop("_corrupt", None)
    reg["courses"][key] = {
        "path": str(root),
        "term": course.get("term", ""),
        "title": course.get("title", ""),
    }
    save_registry(reg)
    return key


def unregister(key):
    reg = load_registry()
    reg.pop("_corrupt", None)
    existed = reg["courses"].pop(key, None) is not None
    save_registry(reg)
    return existed


def lookup(name):
    """Registry lookup: exact key first, then a forgiving match on course number.

    Typing '326' should find 'COMPSCI 326', and it should never silently pick one
    of two matches. An ambiguous name is an error, not a coin flip.
    """
    reg = load_registry()
    courses = reg["courses"]
    if name in courses:
        return Path(courses[name]["path"])

    norm = re.sub(r"[^a-z0-9]", "", name.lower())
    hits = sorted({v["path"] for k, v in courses.items()
                   if norm and norm in re.sub(r"[^a-z0-9]", "", k.lower())})
    if len(hits) == 1:
        return Path(hits[0])
    if len(hits) > 1:
        sys.exit(f"{name!r} matches several registered courses:\n  "
                 + "\n  ".join(hits)
                 + "\nUse the full path or a more specific name.")
    return None


# ------------------------------------------------------------------- locating

def resolve(path, allow_missing=True):
    """Find the course root from a path inside the course tree, or from a name.

    Accepts <root>/326, <root>/326/.infra, <root>/326/.infra/piazza and returns
    <root>/326 for all three. People type whichever one they were just looking at,
    and making them retype the right level is friction with no safety benefit.

    Also accepts a bare name like '326', resolved through the registry and then
    against the configured courses root. That is what lets every other script take
    --course 326 without the user tracking where the folder lives.
    """
    if not path:
        path = os.environ.get("COURSE_DIR")
    if not path:
        sys.exit(
            "No course given. Pass --course <name-or-path>, or set COURSE_DIR.\n"
            "A name like '326' works once the course is registered; "
            "run `course_infra.py list` to see what is."
        )

    text = str(path)
    looks_like_path = os.sep in text or text.startswith("~") or text.startswith(".")

    if not looks_like_path:
        found = lookup(text)
        if found and found.is_dir():
            return found.resolve()
        candidate = courses_root() / text
        if (candidate / INFRA).is_dir():
            return candidate.resolve()
        # A bare name is a course name, not a relative path. An unknown one belongs
        # under the courses root, which is where init should create it -- resolving
        # it against the current directory would scatter courses wherever the shell
        # happened to be sitting.
        if not allow_missing:
            sys.exit(f"No course named {text!r}. Checked the registry and "
                     f"{courses_root()}.\nRun `course_infra.py list` to see what is "
                     f"registered, or pass a path.")
        return candidate

    p = Path(text).expanduser()
    p = p.resolve() if p.exists() else Path(os.path.abspath(os.path.expanduser(text)))

    if (p / INFRA).is_dir():
        return p
    if p.name == INFRA:
        return p.parent
    if p.parent.name == INFRA:
        return p.parent.parent
    for ancestor in p.parents:
        if (ancestor / INFRA).is_dir():
            return ancestor

    if not allow_missing and not p.exists():
        sys.exit(f"No course found for {text!r}. "
                 f"Checked the registry, {courses_root()}, and the path itself.")
    return p  # new course; init will create .infra here


def infra(root):
    return root / INFRA


def tool_dir(root, tool):
    return infra(root) / tool


def course_json_path(root):
    return infra(root) / COURSE_JSON


def load_course(root):
    p = course_json_path(root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        sys.exit(f"{p} is not valid JSON: {e}")


def save_course(root, data):
    course_json_path(root).write_text(json.dumps(data, indent=2) + "\n")


def load_config(root, tool):
    p = tool_dir(root, tool) / CONFIG
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        sys.exit(f"{p} is not valid JSON: {e}")


def save_config(root, tool, cfg):
    (tool_dir(root, tool) / CONFIG).write_text(json.dumps(cfg, indent=2) + "\n")


def profile_path(root):
    """Shared course knowledge. Under .infra by default; the course root is
    accepted as a fallback so an instructor who keeps it alongside the syllabus
    is not punished for it."""
    for candidate in (infra(root) / PROFILE, root / PROFILE):
        if candidate.exists():
            return candidate
    for base in (infra(root), root):
        if base.is_dir():
            found = sorted(base.glob("course-profile*.md"))
            if found:
                return found[0]
    return None


def configured_tools(root):
    if not infra(root).is_dir():
        return []
    return sorted(d.name for d in infra(root).iterdir()
                  if d.is_dir() and not d.name.startswith("."))


# ---------------------------------------------------------------- credentials

def load_credentials(root, tool):
    """Read a tool's credentials: the course's own file first, environment second.

    Every client script shares this, so the rules are identical everywhere. Returns
    whatever it found; the caller decides which keys it cannot live without, since
    that varies by operation.
    """
    values = {}
    cred = tool_dir(Path(root), tool) / CREDENTIALS
    if cred.exists():
        for line in cred.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip("'\"")
            if v:
                values[k.strip()] = v

    known = TOOLS.get(tool, {}).get("credentials", []) + EXTRA_CREDENTIAL_KEYS.get(tool, [])
    for key in known:
        if not values.get(key) and os.environ.get(key):
            values[key] = os.environ[key]
    return values


def require_credentials(root, tool, keys):
    """Fetch credentials or exit with a message naming the real file to edit."""
    values = load_credentials(root, tool)
    missing = [k for k in keys if not values.get(k)]
    if missing:
        cred = tool_dir(Path(root), tool) / CREDENTIALS
        sys.exit(f"Missing {', '.join(missing)} for {tool}.\n"
                 f"Fill them into {cred} (chmod 600), or export them as "
                 f"environment variables.")
    return values


def log_action(root, tool, entry):
    """Append one write to the tool's audit log. Every mutation goes through here,
    and every entry carries enough of the previous state to reconstruct an undo."""
    from datetime import datetime, timezone
    td = tool_dir(Path(root), tool)
    td.mkdir(parents=True, exist_ok=True)
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    with (td / ACTIONS).open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


# ------------------------------------------------------------------- creating

def init(root, tool=None, course_name=None, term=None, title=None,
         institution=None, layout=True, naming=None, add_folders=(),
         skip_folders=(), **tool_config):
    """Create the layout. Safe to re-run; never overwrites an existing file."""
    created = []

    if not infra(root).is_dir():
        infra(root).mkdir(parents=True)
        created.append(f"{INFRA}/")

    gi = infra(root) / ".gitignore"
    if not gi.exists():
        gi.write_text(GITIGNORE)
        created.append(f"{INFRA}/.gitignore")

    if not course_json_path(root).exists():
        save_course(root, {
            "course_number": course_name or root.name,
            "title": title or "",
            "term": term or "",
            "institution": institution or "",
        })
        created.append(f"{INFRA}/{COURSE_JSON}")
    else:
        c = load_course(root)
        for key, val in (("course_number", course_name), ("term", term),
                         ("title", title), ("institution", institution)):
            if val and not c.get(key):
                c[key] = val
        save_course(root, c)

    if layout:
        created += ensure_layout(root, term=term, naming=naming,
                                 add=add_folders, remove=skip_folders)

    if not tool:
        return created

    if tool not in TOOLS:
        sys.exit(f"Unknown tool {tool!r}. Known tools: {', '.join(sorted(TOOLS))}")

    td = tool_dir(root, tool)
    for sub in (INBOX, DRAFTS, STATE):
        d = td / sub
        if not d.exists():
            d.mkdir(parents=True)
            created.append(f"{INFRA}/{tool}/{sub}/")

    cred = td / CREDENTIALS
    if not cred.exists():
        cred.write_text(credentials_template(tool))
        cred.chmod(0o600)
        created.append(f"{INFRA}/{tool}/credentials (fill this in)")

    cfg_path = td / CONFIG
    supplied = {k: v for k, v in tool_config.items() if v}
    if not cfg_path.exists():
        cfg = dict(TOOLS[tool]["config"])
        cfg.update({k: v for k, v in supplied.items() if k in cfg})
        save_config(root, tool, cfg)
        created.append(f"{INFRA}/{tool}/{CONFIG}")
    else:
        cfg = load_config(root, tool)
        changed = False
        for k, v in supplied.items():
            if k in TOOLS[tool]["config"] and not cfg.get(k):
                cfg[k] = v
                changed = True
        if changed:
            save_config(root, tool, cfg)

    return created


# ----------------------------------------------------------------- inspecting

def profile_identities(text):
    """Pull every service identity the profile mentions, so verify can cross-check
    each tool's config against the one document a human actually reads."""
    found = {}
    for tool, spec in TOOLS.items():
        pattern = spec.get("identity_pattern")
        if not pattern:
            continue
        m = re.search(pattern, text)
        if m:
            found[tool] = m.group(1)
    return found


def describe(root, tool=None):
    """What is actually here. Used to confirm this is the right course before
    reading from it or writing to a service on its behalf."""
    info = {"root": str(root), "exists": root.is_dir(), "problems": []}
    if not info["exists"]:
        info["problems"].append("course folder does not exist")
        return info
    if not infra(root).is_dir():
        info["problems"].append(f"no {INFRA}/ in this folder; run init first")
        return info

    course = load_course(root)
    info["course"] = course
    info["course_number"] = course.get("course_number") or root.name
    info["title"] = course.get("title", "")
    info["term"] = course.get("term", "")
    info["institution"] = course.get("institution", "")
    info["tools"] = configured_tools(root)
    info["registered"] = any(Path(v["path"]) == root
                             for v in load_registry()["courses"].values())

    info["layout"] = layout_status(root)
    if not info["layout"]["exists"]:
        info["problems"].append(
            "no course/ folder; run `course_infra.py layout <course>` to create it")
    elif info["layout"]["durable_missing"] or info["layout"]["per_term_missing"]:
        gone = info["layout"]["durable_missing"] + info["layout"]["per_term_missing"]
        info["problems"].append(
            f"layout folders configured but missing on disk: {', '.join(gone)}; "
            f"run `course_infra.py layout <course>`")

    prof = profile_path(root)
    info["profile"] = str(prof) if prof else None
    info["profile_ids"] = {}
    if prof:
        text = prof.read_text()
        info["profile_title"] = next((l.strip("# \n") for l in text.splitlines() if l.strip()), "")
        info["profile_ids"] = profile_identities(text)
    else:
        info["problems"].append(f"no {PROFILE} in {INFRA}/ or the course root")

    info["tool_reports"] = {}
    for t in ([tool] if tool else info["tools"]):
        if not tool_dir(root, t).is_dir():
            info["problems"].append(f"{t} is not set up here; run init --tool {t}")
            continue
        rep, probs = describe_tool(root, t, info["profile_ids"].get(t))
        info["tool_reports"][t] = rep
        info["problems"] += probs

    return info


def describe_tool(root, tool, profile_identity=None):
    td = tool_dir(root, tool)
    cfg = load_config(root, tool)
    spec = TOOLS.get(tool, {})
    problems = []
    rep = {"path": str(td), "config": cfg, "label": spec.get("label", tool)}

    for key in spec.get("required_config", []):
        if not cfg.get(key):
            problems.append(f"{tool}/config.json has no {key}")

    # Credentials: present, complete, and not readable by everyone on the machine.
    cred = td / CREDENTIALS
    values = load_credentials(root, tool)
    needed = spec.get("credentials", [])
    if tool == "gradescope" and values.get("GRADESCOPE_SESSION"):
        needed = ["GRADESCOPE_SESSION"]  # the SSO path replaces the password
    missing = [k for k in needed if not values.get(k)]

    if cred.exists():
        mode = stat.S_IMODE(cred.stat().st_mode)
        if mode & 0o077:
            problems.append(f"{tool}/credentials is {oct(mode)}; other users on this "
                            f"machine can read it. Run: chmod 600 {cred}")

    if missing:
        rep["credentials"] = "incomplete"
        problems.append(f"{tool} credentials missing {', '.join(missing)}")
    elif cred.exists():
        rep["credentials"] = str(cred)
    elif values:
        rep["credentials"] = "environment variables"
    else:
        rep["credentials"] = None
        problems.append(f"no credentials found for {tool}")

    # The check that matters most: the shared profile and this tool's config must
    # name the same class. This is what catches a folder copied from last term.
    ident_key = spec.get("identity_key")
    if ident_key:
        rep["identity"] = cfg.get(ident_key, "")
        if profile_identity and rep["identity"] and profile_identity not in str(rep["identity"]):
            problems.append(
                f"MISMATCH: the course profile names {tool} {profile_identity} but "
                f"{tool}/config.json says {rep['identity']}. "
                f"Resolve this before writing anything.")

    for mode_key in ("privatize_mode", "write_mode"):
        if mode_key in cfg:
            rep[mode_key] = cfg[mode_key]

    inbox = sorted((td / INBOX).glob("*.json")) if (td / INBOX).is_dir() else []
    drafts = [d for d in (td / DRAFTS).glob("*") if d.is_file()] if (td / DRAFTS).is_dir() else []
    rep["inbox_count"] = len(inbox)
    rep["latest_inbox"] = str(inbox[-1]) if inbox else None
    rep["draft_count"] = len(drafts)

    seen = td / SEEN
    rep["seen_count"] = 0
    if seen.exists():
        try:
            rep["seen_count"] = len(json.loads(seen.read_text()).get("seen", []))
        except json.JSONDecodeError:
            problems.append(f"{tool}/state/seen.json is corrupt; delete it to reset")

    actions = td / ACTIONS
    rep["action_count"] = 0
    rep["last_action"] = None
    if actions.exists():
        lines = [l for l in actions.read_text().splitlines() if l.strip()]
        rep["action_count"] = len(lines)
        if lines:
            try:
                rep["last_action"] = json.loads(lines[-1])
            except json.JSONDecodeError:
                pass

    return rep, problems


def format_description(info):
    if not info["exists"]:
        return f"{info['root']} does not exist."

    header = " ".join(x for x in (info.get("course_number", ""), info.get("title") or "") if x)
    if info.get("term"):
        header += f" ({info['term']})"

    lines = [f"Course: {header.strip() or '(unnamed)'}",
             f"  root:        {info['root']}",
             f"  profile:     {info.get('profile_title') or 'MISSING'}",
             f"  registered:  {'yes' if info.get('registered') else 'no'}",
             f"  tools:       {', '.join(info.get('tools') or []) or 'none configured'}"]

    lay = info.get("layout") or {}
    if lay.get("exists"):
        lines.append(f"  naming:      {lay['naming']}")
        lines.append(f"  semester:    {lay.get('semester') or '(not set)'}"
                     + (f"  [current -> {lay['current_link']}]" if lay.get("current_link") else ""))
        lines.append(f"  course/:     {', '.join(lay['durable_present']) or 'empty'}")
        if lay.get("per_term_present"):
            lines.append(f"  semester/:   {', '.join(lay['per_term_present'])}")
        if lay.get("unlisted"):
            lines.append(f"  unlisted:    {', '.join(lay['unlisted'])}")

    for tool, rep in (info.get("tool_reports") or {}).items():
        lines.append(f"  [{rep.get('label', tool)}]")
        if rep.get("identity") is not None:
            lines.append(f"    class:       {rep.get('identity') or '(not set)'}")
        lines.append(f"    credentials: {rep.get('credentials') or 'MISSING'}")
        for mode_key in ("privatize_mode", "write_mode"):
            if mode_key in rep:
                lines.append(f"    {(mode_key + ':').ljust(12)} {rep[mode_key]}")
        lines.append(f"    inbox:       {rep['inbox_count']} file(s)"
                     + (f", latest {Path(rep['latest_inbox']).name}" if rep["latest_inbox"] else ""))
        lines.append(f"    drafts:      {rep['draft_count']} pending")
        lines.append(f"    seen:        {rep['seen_count']} item(s) already handled")
        la = rep.get("last_action")
        lines.append("    last write:  "
                     + (f"{la.get('action')} on {la.get('cid') or la.get('target')} "
                        f"at {la.get('at')}" if la else "none"))

    if info["problems"]:
        lines.append("  problems:")
        lines += [f"    - {p}" for p in info["problems"]]
    return "\n".join(lines)


def format_list():
    reg = load_registry()
    lines = [f"Courses root: {reg['courses_root']}"]
    if reg.get("_corrupt"):
        lines.append(f"  (the registry at {REGISTRY} is corrupt and is being ignored)")
    if not reg["courses"]:
        lines.append("  no courses registered yet")
        return "\n".join(lines)

    for key, val in sorted(reg["courses"].items()):
        root = Path(val["path"])
        state = "ok" if (root / INFRA).is_dir() else "MISSING"
        tools = ", ".join(configured_tools(root)) or "no tools"
        term = val.get("term") or ""
        lines.append(f"  {key.ljust(20)} {val['path']}")
        lines.append(f"  {''.ljust(20)} {term + '  ' if term else ''}{tools}  [{state}]")
    return "\n".join(lines)


# --------------------------------------------------------------------- the CLI

def main():
    ap = argparse.ArgumentParser(description="Set up and check a course's .infra folder.")
    ap.add_argument("command",
                    choices=["init", "verify", "list", "register", "unregister",
                             "set-root", "path", "layout"])
    ap.add_argument("course", nargs="?", help="Course name or folder")
    ap.add_argument("--tool", help="Service to set up or check: " + ", ".join(sorted(TOOLS)))
    ap.add_argument("--name", help="Course number or short name")
    ap.add_argument("--title", help="Course title")
    ap.add_argument("--term", help="Term, e.g. 'Fall 2026'")
    ap.add_argument("--institution", help="Institution")
    ap.add_argument("--course-url", help="Piazza: the class URL")
    ap.add_argument("--base-url", help="Canvas: e.g. https://umass.instructure.com")
    ap.add_argument("--course-id", help="Canvas or Gradescope: the numeric course id")
    ap.add_argument("--naming", choices=sorted(NAMING_STYLES),
                    help="Folder naming style for this course (default kebab)")
    ap.add_argument("--add-folder", action="append", default=[], metavar="NAME",
                    help="Extra folder to create; repeatable")
    ap.add_argument("--skip-folder", action="append", default=[], metavar="NAME",
                    help="Default folder to leave out; repeatable")
    ap.add_argument("--no-layout", action="store_true",
                    help="init: create .infra only, no course material folders")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    if args.command == "list":
        print(json.dumps(load_registry(), indent=2) if args.json else format_list())
        return 0

    if args.command == "set-root":
        if not args.course:
            sys.exit("Give the folder your courses live in, e.g. set-root ~/courses")
        print(f"Courses root is now {set_courses_root(args.course)}")
        return 0

    if args.command == "unregister":
        if not args.course:
            sys.exit("Give the registered name to remove.")
        print(f"Removed {args.course}" if unregister(args.course)
              else f"{args.course} was not registered")
        return 0

    if args.command == "path":
        print(resolve(args.course, allow_missing=False))
        return 0

    root = resolve(args.course)

    if args.command == "init":
        root.mkdir(parents=True, exist_ok=True)
        created = init(root, tool=args.tool, course_name=args.name, term=args.term,
                       title=args.title, institution=args.institution,
                       layout=not args.no_layout, naming=args.naming,
                       add_folders=args.add_folder, skip_folders=args.skip_folder,
                       course_url=args.course_url, base_url=args.base_url,
                       course_id=args.course_id)
        key = register(root, args.name)
        print(f"Initialized {root}")
        for c in created:
            print(f"  created {c}")
        if not created:
            print("  (already set up, nothing to do)")
        print(f"  registered as {key!r}; `--course {key}` works from now on")
        print()

    if args.command == "layout":
        created = ensure_layout(root, term=args.term, naming=args.naming,
                                add=args.add_folder, remove=args.skip_folder)
        print(f"Layout for {root}")
        for c in created:
            print(f"  created {c}")
        if not created:
            print("  (already in place, nothing to do)")
        print()

    if args.command == "register":
        key = register(root, args.name)
        print(f"Registered {root} as {key!r}\n")

    info = describe(root, args.tool)
    print(json.dumps(info, indent=2) if args.json else format_description(info))
    return 1 if info["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
