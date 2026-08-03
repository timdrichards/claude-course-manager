#!/usr/bin/env python3
"""Shared helpers for every Canvas script in this plugin.

This module exists because the same roster-matching code was once copy-pasted
into two scripts, and the test suite grew a dedicated parity test to stop them
drifting apart. A test that asserts two copies are identical is a sign the copies
should be one thing. Now they are, and the parity test is redundant by
construction rather than by vigilance.

Everything here is I/O-light and import-safe: no network at import time, no
config read at import time, so the test suite can import it freely.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANVAS_PY = str(HERE / "canvas.py")
sys.path.insert(0, str(HERE))

# Column names Gradescope and friends actually use, in preference order.
SCORE_CANDIDATES = ["Total Score", "Score"]
EMAIL_CANDIDATES = ["Email", "Email Address"]
SID_CANDIDATES = ["SID", "Student ID", "Student SID"]
MAXPTS_CANDIDATES = ["Max Points", "Maximum Points"]
STATUS_CANDIDATES = ["Status", "Submission Status"]


def die(message, detail=None, code=1):
    err = {"error": message}
    if detail is not None:
        err["detail"] = detail
    print(json.dumps(err, indent=2), file=sys.stderr)
    sys.exit(code)


# --------------------------------------------------------------- global flags

GLOBAL_DEFAULTS = {"course": None, "course_id": None, "dry_run": False,
                   "live": False, "override_mode": False}


def global_flags(write=True, dry_run=True):
    """The flags every wrapper shares, on a parent parser. Same shape as canvas.py.

    Two details carry the whole thing, and both are easy to lose in a rewrite.
    Putting these on a *parent* parser and passing it to every subparser is what
    makes `groups.py assign teams.json --live` work: argparse otherwise rejects a
    top-level flag that appears after the subcommand, and after the subcommand is
    where everybody types it. argparse.SUPPRESS is the other half -- without it a
    subparser writes its own default over a value the top-level parser already
    collected, so `rubric.py --course 326 grade g.json` would silently lose the
    course and fall back to the environment.

    This lives here rather than being copy-pasted into five scripts for the reason
    in this module's docstring: five copies of a subtle argparse idiom drift, and
    the drift is invisible until a flag quietly stops working.
    """
    S = argparse.SUPPRESS
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--course", default=S,
                   help="Course name or folder (see `course_infra.py list`)")
    p.add_argument("--course-id", default=S,
                   help="Canvas course id, overriding the course folder's config")
    if dry_run:
        p.add_argument("--dry-run", action="store_true", default=S,
                       help="Preview only; send nothing and write nothing")
    if write:
        p.add_argument("--live", action="store_true", default=S,
                       help="Actually send the write to Canvas")
        p.add_argument("--override-mode", action="store_true", default=S,
                       help="Allow a write although the course config says dry-run")
    return p


def apply_global_defaults(args):
    """SUPPRESS means an unsupplied flag leaves no attribute on the namespace at
    all. Fill the missing ones in once, here, so every call site can just read
    args.live without a getattr dance."""
    for key, default in GLOBAL_DEFAULTS.items():
        if not hasattr(args, key):
            setattr(args, key, default)
    return args


# ------------------------------------------------------------------ the CLI

def canvas_cli(cli_args, course=None, live=False, override=False):
    """Call canvas.py and return (parsed_json, error).

    Course, --live, and --override-mode are threaded through here so a caller
    never has to remember them, and so the gate in canvas.py is the single place
    a write can be authorized. A wrapper script that forgets to pass live=True
    produces a dry run, which is the safe direction to fail in.
    """
    argv = [sys.executable, CANVAS_PY]
    if course:
        argv += ["--course", str(course)]
    if live:
        argv += ["--live"]
    if override:
        argv += ["--override-mode"]
    argv += list(cli_args)

    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        try:
            detail = json.loads(result.stderr)
        except json.JSONDecodeError:
            detail = result.stderr.strip()
        return None, detail
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, f"canvas.py returned non-JSON output: {result.stdout[:500]!r}"


def canvas_get(path, course=None, params=None, all_pages=True):
    """The common read. Returns parsed JSON or dies with Canvas's own message."""
    argv = ["get", path]
    for p in params or []:
        argv += ["--param", p]
    if all_pages:
        argv += ["--all"]
    data, err = canvas_cli(argv, course=course)
    if err:
        die(f"Canvas read failed: {path}", err, code=2)
    return data


def resolve_course_id(course=None, explicit=None):
    """The course id for a wrapper's --course-id argument.

    Explicit flag wins, then the course folder's canvas config, then the
    environment. Wrappers should call this instead of defaulting an argparse
    argument to os.environ, which is how the old scripts each grew their own
    slightly different version of this.
    """
    if explicit:
        return str(explicit)
    if course:
        try:
            import course_infra
            root = course_infra.resolve(course)
            cid = course_infra.load_config(root, "canvas").get("course_id")
            if cid:
                return str(cid)
        except Exception:
            pass
    env = os.environ.get("CANVAS_COURSE_ID", "")
    if env:
        return env
    die("No course id",
        "Pass --course <name> (with course_id set in its canvas/config.json), "
        "or --course-id, or export CANVAS_COURSE_ID.")


def course_root(course=None):
    """The course folder, or None when running from environment variables."""
    if not course:
        return None
    try:
        import course_infra
        return course_infra.resolve(course)
    except Exception:
        return None


def canvas_token(course=None):
    """The Canvas API token: the course folder's credentials first, environment second.

    Only canvas.py is supposed to touch auth, and for anything that goes through
    canvas.py it still is. download_submissions.py is the one real exception --
    Canvas's attachment URLs are fetched directly, so that script needs the token
    in hand for the 401/403 fallback. Reading it here rather than off os.environ
    means the exception still honours the course folder, and exactly one function,
    not one script, knows where a token lives.

    Returns "" when there is no token; the caller decides whether it can proceed
    without one, since a dry run can.
    """
    root = course_root(course)
    if root is not None:
        try:
            import course_infra
            creds = course_infra.load_credentials(root, "canvas")
            token = creds.get("CANVAS_TOKEN") or creds.get("CANVAS_API_TOKEN")
            if token:
                return token
        except Exception:
            pass  # fall through to the environment, same as canvas.py does
    return (os.environ.get("CANVAS_API_TOKEN")
            or os.environ.get("CANVAS_TOKEN") or "")


def log_action(course, action, target, before=None, after=None, **extra):
    """Record a write in the course's audit log, if there is a course folder."""
    root = course_root(course)
    if root is None:
        return None
    try:
        import course_infra
        return course_infra.log_action(root, "canvas", {
            "action": action, "target": str(target),
            "before": before, "after": after, **extra})
    except Exception as e:
        print(json.dumps({"warning": f"could not write actions.log: {e}"}),
              file=sys.stderr)
        return None


def write_mode(course=None):
    try:
        import course_infra
        root = course_infra.resolve(course) if course else None
        if root is None:
            return None
        return course_infra.load_config(root, "canvas").get("write_mode", "dry-run")
    except Exception:
        return None


def confirm_write(course, live, override=False, what=""):
    """The gate, for wrappers that do their own writing rather than shelling out.

    Mirrors canvas.py's rule exactly: --live plus the course config, or --live
    alone when there is no course folder to consult.
    """
    if not live:
        print(json.dumps({"dry_run": True, "note": f"No --live, so {what or 'nothing'} "
                          f"was not sent to Canvas."}, indent=2), file=sys.stderr)
        return False
    mode = write_mode(course)
    if mode is None:
        return True  # environment-variable mode; --live carries it
    if mode != "live" and not override:
        die(f"write_mode is {mode!r} for this course",
            "Set it to \"live\" in the course's canvas/config.json once you have "
            "watched this do the right thing, or pass --override-mode.", code=4)
    return True


def should_write(args, what=""):
    """Decide, once, whether this run may write. False means print the preview.

    --dry-run wins outright, so it keeps working as the plain "show me" switch it
    always was even when someone leaves --live in their shell history. Otherwise
    the gate above decides, and dies rather than returning False when the course
    config forbids the write -- a refused write is an error, an unrequested one is
    just a preview, and the two should not look alike.
    """
    if getattr(args, "dry_run", False):
        return False
    return confirm_write(args.course, args.live, args.override_mode, what=what)


# ------------------------------------------------------------------- CSV

def load_csv(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            return reader.fieldnames or [], rows
    except FileNotFoundError:
        die(f"CSV not found: {path}")
    except (csv.Error, UnicodeDecodeError) as e:
        die(f"Could not read CSV {path}", str(e))


def load_json_file(path, what="file"):
    """Reading a config file should fail like every other error here: as JSON on
    stderr, not as a traceback."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        die(f"{what} not found: {path}")
    except json.JSONDecodeError as e:
        die(f"{what} is not valid JSON: {path}", str(e))


def pick_column(headers, explicit, candidates, what, required=True):
    if explicit:
        if explicit not in headers:
            die(f"--{what}-column {explicit!r} not found in the CSV",
                {"available_columns": headers})
        return explicit
    for c in candidates:
        if c in headers:
            return c
    if required:
        die(f"Could not autodetect the {what} column",
            {"looked_for": candidates, "available_columns": headers,
             "hint": f"pass --{what}-column"})
    return None


def fmt_score(value):
    """Canvas wants "45", not "45.0"; a trailing .0 shows up in the gradebook."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# ------------------------------------------------------- identity matching

def build_roster_maps(users):
    """From Canvas /users rows, build lookup maps and flag duplicate keys.

    Every key gets duplicate tracking, not just email: any of them can decide a
    grade, so any of them being ambiguous has to be visible to match_row rather
    than silently resolved by whichever roster row happened to come last.
    """
    by_email, by_sis, by_login = {}, {}, {}
    dup_email, dup_sis, dup_login = set(), set(), set()
    id_to_name = {}
    for u in users:
        uid = u.get("id")
        if uid is None:
            continue
        id_to_name[uid] = u.get("name") or u.get("sortable_name") or str(uid)
        email = (u.get("email") or "").strip().lower()
        if email:
            if email in by_email and by_email[email] != uid:
                dup_email.add(email)
            by_email[email] = uid
        sis = str(u.get("sis_user_id") or "").strip()
        if sis:
            if sis in by_sis and by_sis[sis] != uid:
                dup_sis.add(sis)
            by_sis[sis] = uid
        login = (u.get("login_id") or "").strip().lower()
        if login:
            if login in by_login and by_login[login] != uid:
                dup_login.add(login)
            by_login[login] = uid
    return {"email": by_email, "sis": by_sis, "login": by_login,
            "dup_email": dup_email, "dup_sis": dup_sis, "dup_login": dup_login,
            "name": id_to_name}


def match_row(row, cols, maps):
    """Resolve one CSV row to a Canvas user id. Returns (user_id, how) or (None, reason).

    Keys are tried most-reliable first: the email column, then the SID against
    `sis_user_id`, then the email again as a login id.

    A key that matches *more than one* Canvas user is skipped rather than
    guessed -- but a later, unambiguous key can still resolve the row. A shared
    family email with distinct student ids is the case that matters: the email
    can't identify anyone, the SID identifies exactly one person, so the SID
    wins. Only a row that no unambiguous key resolves is reported unmatched,
    and the reason names which keys were ambiguous.

    Never match on name. Names collide, change, and are formatted differently in
    every system, and a name-matched grade batch eventually lands on the wrong
    person.
    """
    email = (row.get(cols["email"]) or "").strip().lower() if cols.get("email") else ""
    sid = (row.get(cols["sid"]) or "").strip() if cols.get("sid") else ""
    login = email  # Gradescope email often equals the Canvas login id too

    ambiguous = []

    if email:
        if email in maps["dup_email"]:
            ambiguous.append("email")
        elif email in maps["email"]:
            return maps["email"][email], "email"
    if sid:
        if sid in maps["dup_sis"]:
            ambiguous.append("sid")
        elif sid in maps["sis"]:
            return maps["sis"][sid], "sis"
    if login and "email" not in ambiguous:
        if login in maps["dup_login"]:
            ambiguous.append("login_id")
        elif login in maps["login"]:
            return maps["login"][login], "login_id"

    if ambiguous:
        return None, "ambiguous_" + "_and_".join(ambiguous)
    return None, "no_match"


# Kept for the scripts that imported it under the old name.
match_identity = match_row
