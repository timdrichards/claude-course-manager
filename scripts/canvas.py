#!/usr/bin/env python3
"""canvas.py: a thin, reliable CLI for the Canvas LMS REST and GraphQL APIs.

Handles the mechanical parts so the caller can focus on which endpoint and what
payload: authentication, pagination (Link headers), rate limit backoff, JSON
encoding, and the write gate.

Every other Canvas script in this plugin goes through this file. Auth, retries,
and pagination live here once, which is why a bug fixed here is fixed for all of
them.

Configuration, in priority order:

  1. A course folder.  --course 326  reads base_url and course_id from
     <course>/.infra/canvas/config.json and CANVAS_TOKEN from that folder's
     credentials file. This is the documented path.
  2. Environment variables, for CI or for someone with no course folder:
       CANVAS_BASE_URL    e.g. https://school.instructure.com
       CANVAS_API_TOKEN   (CANVAS_TOKEN is also accepted)
       CANVAS_COURSE_ID   substitutes :course in paths

Writes are gated. A write needs --live, and when it runs against a course folder
that folder's config.json must also say "write_mode": "live". Without --live the
command prints the request it would have sent and stops. Two switches rather than
one: the flag is easy to type by accident, the config file is a decision made once
and deliberately. Every write is appended to <course>/.infra/canvas/actions.log.

Usage:
  canvas.py get    <path> [--param k=v ...] [--all] [--page-size N]
  canvas.py post   <path> [--json '<json>' | --json-file f] [--form] [--live]
  canvas.py put    <path> [--json '<json>' | --json-file f] [--form] [--live]
  canvas.py delete <path> [--param k=v ...] [--live]
  canvas.py graphql '<query>' [--vars '<json>']

Examples:
  canvas.py --course 326 get /courses/:course/students --all
  canvas.py --course 326 get /courses/:course/assignments --all --param search_term=HW
  canvas.py --course 326 put /courses/:course/assignments/123 \\
      --json '{"assignment": {"published": true}}' --live

Output: JSON on stdout. Errors: JSON on stderr, nonzero exit code.
With --all, paginated results are merged into a single JSON array.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

API_PREFIX = "/api/v1"
RATE_LIMIT_FLOOR = 50.0   # back off when X-Rate-Limit-Remaining drops below this
MAX_RETRIES = 5
TIMEOUT = 30              # seconds; without this a hung connection blocks forever
TOOL = "canvas"


def die(message, detail=None, code=1):
    err = {"error": message}
    if detail is not None:
        err["detail"] = detail
    print(json.dumps(err, indent=2), file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------- config

def load_config(course=None):
    """Resolve Canvas config from a course folder, falling back to the environment.

    Returns the dict every other function here takes: base, token, course, plus
    root and write_mode when a course folder was used (the gate needs those, and
    env-var callers simply do not have them).
    """
    base = token = course_id = ""
    root = None
    write_mode = None

    if course:
        try:
            import course_infra
        except ImportError:
            die("course_infra.py is not importable",
                "It must sit next to canvas.py in the plugin's scripts/ folder.")
        root = course_infra.resolve(course)
        cfg = course_infra.load_config(root, TOOL)
        base = (cfg.get("base_url") or "").rstrip("/")
        course_id = str(cfg.get("course_id") or "")
        write_mode = cfg.get("write_mode", "dry-run")
        creds = course_infra.load_credentials(root, TOOL)
        token = creds.get("CANVAS_TOKEN") or creds.get("CANVAS_API_TOKEN") or ""

    # Environment fills any gap, so a half-configured folder still works and CI
    # needs no folder at all.
    base = base or os.environ.get("CANVAS_BASE_URL", "").rstrip("/")
    token = (token or os.environ.get("CANVAS_API_TOKEN")
             or os.environ.get("CANVAS_TOKEN") or "")
    course_id = course_id or os.environ.get("CANVAS_COURSE_ID", "")

    if not base:
        die("No Canvas base URL",
            f"Set base_url in {root}/.infra/canvas/config.json" if root
            else "export CANVAS_BASE_URL=https://your.instructure.com")
    if not token:
        die("No Canvas API token",
            f"Put CANVAS_TOKEN in {root}/.infra/canvas/credentials" if root
            else "Generate one in Canvas: Account > Settings > New Access Token")

    return {"base": base, "token": token, "course": course_id,
            "root": root, "write_mode": write_mode}


def resolve_path(path, config):
    """Substitute :course with the course id and normalize the path."""
    if ":course" in path:
        if not config["course"]:
            die(":course used in path but no course id is set",
                "Pass --course, or set course_id in the folder's canvas/config.json, "
                "or export CANVAS_COURSE_ID.")
        path = path.replace(":course", config["course"])
    if not path.startswith("/"):
        path = "/" + path
    if not path.startswith(API_PREFIX) and not path.startswith("/api/"):
        path = API_PREFIX + path
    return path


def parse_params(pairs):
    """Turn repeated k=v flags into a list of (key, value) tuples.

    Repeated keys are preserved, which Canvas uses for array params,
    e.g. --param include[]=email --param include[]=enrollments
    """
    out = []
    for pair in pairs or []:
        if "=" not in pair:
            die(f"Bad --param (expected k=v): {pair}")
        key, _, value = pair.partition("=")
        out.append((key, value))
    return out


def flatten_form(obj, prefix=""):
    """Flatten nested JSON into Canvas bracket notation for form encoding.

    {"assignment": {"name": "HW7", "due_at": null}} becomes
    [("assignment[name]", "HW7")]  (null values are dropped)
    Lists become repeated key[] entries.
    """
    items = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}[{key}]" if prefix else key
            items.extend(flatten_form(value, new_prefix))
    elif isinstance(obj, list):
        for value in obj:
            items.extend(flatten_form(value, f"{prefix}[]"))
    elif obj is None:
        pass
    elif isinstance(obj, bool):
        items.append((prefix, "true" if obj else "false"))
    else:
        items.append((prefix, str(obj)))
    return items


def parse_link_header(header):
    """Extract rel -> url mapping from an RFC 5988 Link header."""
    links = {}
    if not header:
        return links
    for part in header.split(","):
        match = re.search(r'<([^>]+)>;\s*rel="([^"]+)"', part)
        if match:
            links[match.group(2)] = match.group(1)
    return links


def explain(code, detail):
    """Canvas's failure modes are few and each has one likely cause. Naming it
    saves a round of guessing, and two of these are actively misleading without
    the hint."""
    hints = {
        401: "The token is missing, wrong, or expired. Regenerate it in Canvas: "
             "Account > Settings > New Access Token.",
        403: "Either a permission problem or rate limiting -- Canvas signals both "
             "as 403. If the body mentions a rate limit, slow down and retry. "
             "Otherwise check that the token's account is a teacher or TA in this "
             "course, and that the course is not concluded (concluded courses are "
             "read-only through the API).",
        404: "Canvas returns 404 for objects your token is not allowed to see, not "
             "403. So this is a wrong id OR a permission problem, and the two are "
             "indistinguishable from the response. Never conclude 'it does not "
             "exist' from a 404 alone -- check the token's role first.",
        422: "Canvas rejected the values. The detail below usually names the field.",
    }
    return hints.get(code)


def request(method, url, config, body=None, headers=None):
    """One HTTP request with auth, retries, and rate limit backoff.

    Returns (status, parsed_json_or_none, response_headers).
    """
    all_headers = {
        "Authorization": f"Bearer {config['token']}",
        "Accept": "application/json",
    }
    if headers:
        all_headers.update(headers)

    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(url, data=body, method=method,
                                     headers=all_headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                remaining = resp.headers.get("X-Rate-Limit-Remaining")
                if remaining is not None:
                    try:
                        if float(remaining) < RATE_LIMIT_FLOOR:
                            time.sleep(2)
                    except ValueError:
                        pass
                parsed = json.loads(raw) if raw.strip() else None
                return resp.status, parsed, resp.headers
        except urllib.error.HTTPError as e:
            raw = e.read()
            text = raw.decode("utf-8", "replace")
            # Canvas signals throttling as a 403 whose body mentions a rate limit,
            # which is why the body is checked and not just the status. A 429 is
            # always throttling whatever the body says.
            if e.code == 429 or (e.code == 403 and "Rate Limit" in text):
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
            if e.code in (502, 503) and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            try:
                detail = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                detail = text[:2000]
            hint = explain(e.code, detail)
            if hint:
                detail = {"hint": hint, "canvas_said": detail}
            die(f"HTTP {e.code} from Canvas", detail, code=2)
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            die("Network error reaching Canvas", str(e.reason), code=3)
    die("Exhausted retries against Canvas rate limiting", code=2)


def build_url(config, path, params):
    url = config["base"] + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


# --------------------------------------------------------------- the gate

def check_write_allowed(config, live, override=False, quiet=False):
    """Two switches, both deliberate. Returns True if the write may proceed.

    With a course folder, --live and "write_mode": "live" are both required.
    Without one (env-var mode) there is no config file to consult, so --live
    alone carries it -- but say so, since the weaker guarantee should be visible.
    """
    if not live:
        if not quiet:
            print(json.dumps({
                "dry_run": True,
                "note": "No --live, so nothing was sent to Canvas.",
            }, indent=2), file=sys.stderr)
        return False

    root, mode = config.get("root"), config.get("write_mode")
    if root is None:
        if not quiet:
            print(json.dumps({
                "note": "Running from environment variables, so there is no course "
                        "config to check. --live alone is authorizing this write.",
            }, indent=2), file=sys.stderr)
        return True

    if mode != "live" and not override:
        die(f"write_mode is {mode!r} for this course",
            f"Set it to \"live\" in {root}/.infra/canvas/config.json once you have "
            f"watched this do the right thing, or pass --override-mode for a "
            f"considered one-off.", code=4)
    return True


def log_write(config, action, target, before=None, after=None, **extra):
    """Append one write to the course's audit log. No course folder means no log,
    which is one more reason the folder is the documented path."""
    root = config.get("root")
    if root is None:
        return None
    try:
        import course_infra
        return course_infra.log_action(root, TOOL, {
            "action": action, "target": str(target),
            "before": before, "after": after, **extra})
    except Exception as e:  # logging must never lose a completed write
        print(json.dumps({"warning": f"could not write actions.log: {e}"}),
              file=sys.stderr)
        return None


# ------------------------------------------------------------------ commands

def cmd_get(args, config):
    path = resolve_path(args.path, config)
    params = parse_params(args.param)
    if args.all and not any(k == "per_page" for k, _ in params):
        params.append(("per_page", str(args.page_size)))

    url = build_url(config, path, params)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "method": "GET", "url": url}, indent=2))
        return

    results = []
    single_object = False
    while url:
        _, data, headers = request("GET", url, config)
        if isinstance(data, list):
            results.extend(data)
        else:
            results = data
            single_object = True
        if not args.all or single_object:
            break
        url = parse_link_header(headers.get("Link", "")).get("next")

    print(json.dumps(results, indent=2))


def read_body(args):
    if args.json_file:
        with open(args.json_file) as f:
            return json.load(f)
    if args.json:
        try:
            return json.loads(args.json)
        except json.JSONDecodeError as e:
            die("Invalid JSON in --json", str(e))
    return None


def cmd_write(method, args, config):
    path = resolve_path(args.path, config)
    payload = read_body(args)
    params = parse_params(getattr(args, "param", None))
    url = build_url(config, path, params)

    if args.form and payload is not None:
        body = urllib.parse.urlencode(flatten_form(payload)).encode()
        content_type = "application/x-www-form-urlencoded"
    elif payload is not None:
        body = json.dumps(payload).encode()
        content_type = "application/json"
    else:
        body, content_type = None, None

    # The preview prints either way; the only question is whether the request
    # follows it. Showing it always is what makes a dry run useful.
    preview = {"method": method, "url": url}
    if payload is not None:
        preview["payload"] = payload
        preview["encoding"] = content_type
    if args.dry_run:
        print(json.dumps({"dry_run": True, **preview}, indent=2))
        return

    print(json.dumps({"about_to_send": preview}, indent=2), file=sys.stderr)
    if not check_write_allowed(config, args.live, args.override_mode):
        return

    headers = {"Content-Type": content_type} if content_type else None
    _, data, _ = request(method, url, config, body=body, headers=headers)
    log_write(config, f"{method.lower()} {path}", (data or {}).get("id", path),
              after=payload)
    print(json.dumps(data, indent=2))


def cmd_graphql(args, config):
    url = config["base"] + "/api/graphql"
    payload = {"query": args.query}
    if args.vars:
        try:
            payload["variables"] = json.loads(args.vars)
        except json.JSONDecodeError as e:
            die("Invalid JSON in --vars", str(e))

    # A GraphQL mutation is a write, and the query string is the only place that
    # is visible. Detect it rather than trusting the caller to pass --live.
    if re.match(r"\s*mutation\b", args.query):
        print(json.dumps({"about_to_send": {"graphql_mutation": args.query}},
                         indent=2), file=sys.stderr)
        if not check_write_allowed(config, args.live, args.override_mode):
            return

    body = json.dumps(payload).encode()
    _, data, _ = request("POST", url, config, body=body,
                         headers={"Content-Type": "application/json"})
    print(json.dumps(data, indent=2))


def main():
    # Global flags go on a parent parser so they work before or after the
    # subcommand; argparse otherwise rejects `... put /path --live`, and putting
    # --live last is what everybody types. SUPPRESS keeps the subparser from
    # overwriting a value the top-level parser already collected.
    S = argparse.SUPPRESS
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--course", default=S, help="Course name or folder")
    common.add_argument("--live", action="store_true", default=S,
                        help="Actually send the write")
    common.add_argument("--override-mode", action="store_true", default=S,
                        help="Allow a write although config.json says dry-run")

    parser = argparse.ArgumentParser(description="Canvas LMS API helper",
                                     parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(name, write=False, **kw):
        p = sub.add_parser(name, parents=[common], **kw)
        p.add_argument("path", help="API path, e.g. /courses/:course/assignments")
        p.add_argument("--param", action="append",
                       help="Query param k=v (repeatable; use k[]=v for arrays)")
        p.add_argument("--dry-run", action="store_true",
                       help="Print the request instead of sending it")
        if write:
            p.add_argument("--json", help="JSON payload as a string")
            p.add_argument("--json-file", help="Path to a JSON payload file")
            p.add_argument("--form", action="store_true",
                           help="Send as bracket-encoded form data instead of JSON")
        return p

    p_get = add_common("get")
    p_get.add_argument("--all", action="store_true",
                       help="Follow Link headers and merge all pages")
    p_get.add_argument("--page-size", type=int, default=100,
                       help="per_page value when using --all (default 100)")

    for verb in ("post", "put"):
        add_common(verb, write=True)
    add_common("delete", write=True,
               help="DELETE (destructive; confirm with the user first)")

    p_gql = sub.add_parser("graphql", parents=[common], help="POST a GraphQL query")
    p_gql.add_argument("query")
    p_gql.add_argument("--vars", help="GraphQL variables as JSON")

    args = parser.parse_args()
    for key, default in (("course", None), ("live", False), ("override_mode", False)):
        if not hasattr(args, key):
            setattr(args, key, default)

    config = load_config(args.course)

    if args.command == "get":
        cmd_get(args, config)
    elif args.command == "graphql":
        cmd_graphql(args, config)
    else:
        cmd_write(args.command.upper(), args, config)


if __name__ == "__main__":
    main()
