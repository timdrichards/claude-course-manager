#!/usr/bin/env python3
"""cache_pages.py: write Canvas wiki_page JSON to a local on-disk cache.

Turns page objects already fetched via canvas.py into a local cache of
`<slug>.html` (exact body) + `<slug>.json` (metadata sidecar) files, so later
work in the same project can build on real, current page content instead of
re-deriving or re-fetching it. Never talks to Canvas or handles auth --
canvas.py remains the only thing that does. Nothing here reaches the network and
nothing here can change anything in Canvas, so there is no write gate: --live
would be meaningless and is deliberately absent.

Everything is read and written as UTF-8 explicitly. Canvas page bodies routinely
contain curly quotes, em dashes, and non-Latin names, and Python's open() picks
its codec from the ambient locale -- under a C/POSIX locale that is ASCII, and a
single smart quote in a page body raises UnicodeEncodeError halfway through
caching. The encoding is a property of the file format, not of whoever's shell
happens to be running this.

Usage:
  canvas.py --course 326 get /courses/:course/pages/<slug> | cache_pages.py --course 326
  canvas.py --course 326 get /courses/:course/pages --all --param "include[]=body" \
    | cache_pages.py --course 326
  cache_pages.py --course-id 12345 --input-file pages.json     # no course folder

Reads a single wiki_page JSON object, or a JSON array of them, from stdin
(or --input-file instead of a pipe). Each object should include: url (slug),
title, body, published, updated_at, html_url, id (or page_id). Objects
missing `body` are skipped with a reason, not treated as fatal (the most
common cause is forgetting include[]=body on a list request).

Output: JSON summary on stdout ({"cache_dir", "cached": [...], "skipped": [...]}).
Errors (bad input JSON, no resolvable course id, unwritable cache dir): JSON
on stderr, nonzero exit code.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canvas_common  # noqa: E402

die = canvas_common.die


def read_input(args):
    if args.input_file:
        try:
            raw = Path(args.input_file).read_text(encoding="utf-8")
        except FileNotFoundError:
            die(f"Input file not found: {args.input_file}")
        except UnicodeDecodeError as e:
            die(f"Input file is not valid UTF-8: {args.input_file}", str(e))
    else:
        # Decode stdin ourselves rather than trusting the locale, for the same
        # reason the cache files name their encoding: canvas.py emits UTF-8 JSON
        # whatever LANG says, and a pipeline should not fail on an em dash.
        stream = getattr(sys.stdin, "buffer", None)
        raw = stream.read().decode("utf-8") if stream is not None else sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        die("Invalid JSON on input", str(e))
    return data if isinstance(data, list) else [data]


def cache_one(page, cache_dir, course_id, dry_run):
    title = page.get("title", "<untitled>")
    slug = page.get("url")
    if not slug:
        return None, {"title": title, "reason": "missing url (slug) field"}
    if "/" in slug or "\\" in slug or slug in (".", ".."):
        return None, {"title": title, "reason": f"unsafe slug: {slug!r}"}
    body = page.get("body")
    if body is None:
        return None, {"title": title, "reason": "missing body field (did you forget include[]=body?)"}

    course_dir = os.path.join(cache_dir, str(course_id))
    html_path = os.path.join(course_dir, f"{slug}.html")
    json_path = os.path.join(course_dir, f"{slug}.json")

    content_hash = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    sidecar = {
        "page_id": page.get("page_id", page.get("id")),
        "url": slug,
        "title": title,
        "published": page.get("published"),
        "updated_at": page.get("updated_at"),
        "html_url": page.get("html_url"),
        "content_hash": content_hash,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "course_id": course_id,
    }

    if not dry_run:
        os.makedirs(course_dir, exist_ok=True)
        # encoding="utf-8" on both: the hash above is computed over the UTF-8
        # bytes, so writing the file in any other codec would make the sidecar's
        # content_hash disagree with the file it describes -- when it did not
        # simply raise UnicodeEncodeError first.
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(body)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2)

    return {"slug": slug, "title": title, "content_hash": content_hash, "path": html_path}, None


def main():
    # No --live/--override-mode: this script cannot write to Canvas, and offering
    # a flag that does nothing would teach the wrong habit.
    common = canvas_common.global_flags(write=False)
    parser = argparse.ArgumentParser(
        description="Cache Canvas wiki_page JSON to local .html/.json files",
        parents=[common])
    parser.add_argument("--cache-dir", default="./.canvas-cache",
                        help="Cache root directory (default: ./.canvas-cache)")
    parser.add_argument("--input-file", help="Read JSON from a file instead of stdin")
    args = canvas_common.apply_global_defaults(parser.parse_args())
    course_id = canvas_common.resolve_course_id(args.course, args.course_id)

    pages = read_input(args)

    cached, skipped = [], []
    for page in pages:
        if not isinstance(page, dict):
            skipped.append({"title": "<non-object item>", "reason": "input item is not a JSON object"})
            continue
        result, skip = cache_one(page, args.cache_dir, course_id, args.dry_run)
        if result:
            cached.append(result)
        if skip:
            skipped.append(skip)

    print(json.dumps({
        "cache_dir": os.path.join(args.cache_dir, str(course_id)),
        "dry_run": args.dry_run,
        "cached": cached,
        "skipped": skipped,
    }, indent=2))


if __name__ == "__main__":
    main()
