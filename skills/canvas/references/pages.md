# Pages

Wiki pages are identified by **page url slug** in most endpoints, not numeric
id (though numeric id works too in recent Canvas versions).

## List / read

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages --all --param search_term=syllabus
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages/<url-slug>
```

The list endpoint does **not** include `body`. Fetch the individual page to
get its HTML body. Use `--param "include[]=body"` on the list only if you
truly need every body (slow on large courses).

## Create

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/pages --json '{
  "wiki_page": {
    "title": "Week 5: Middleware",
    "body": "<h2>Overview</h2><p>HTML content here.</p>",
    "published": false,
    "editing_roles": "teachers"
  }
}' --live
```

- `body` is HTML. Convert Markdown before sending.
- The url slug is derived from the title (`week-5-middleware`). Renaming the
  title changes nothing about the existing slug; old links keep working.
- `editing_roles`: `teachers` (default), `students`, `members`, `public`.
- `front_page: true` in the payload sets it as the course front page; only a
  published page can be the front page.

## Update / delete

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/pages/<url-slug> \
    --json '{"wiki_page": {"body": "<p>New content</p>", "published": true}}' --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    delete /courses/:course/pages/<url-slug> --live
```

Updating `body` replaces it entirely. For an edit, GET the current body,
modify, PUT the whole thing back. Page revisions are kept server side
(`/pages/<slug>/revisions`) so mistakes are recoverable, but tell the user
before overwriting substantial content anyway.

## Linking to other Canvas content in page bodies

Use course-relative paths so links survive course copies:

```html
<a href="/courses/:course_id/assignments/123">HW7</a>
```

Canvas's rich content editor uses full URLs; either works, but the API
verifier rewrites `/courses/...` links properly. File links should use the
file's `preview_url` or `/courses/<id>/files/<file_id>` form.

## Generating and uploading a page

This covers authoring a page's HTML and pushing it to Canvas end to end:
picking a title, checking whether it already exists, and creating or updating
it. It is not a new API surface — it composes the Create and Update endpoints
above.

**Inline styles only.** Canvas pages support no `<style>` block, no `<link>`
stylesheet, and no `<script>` tag — see `gotchas.md` #9. Style everything with
inline `style="..."` attributes on the elements themselves. The first time you
generate styled HTML against a given Canvas instance, do a one-time empirical
round-trip check: create a small test page with a representative `style=`
attribute, GET it back, and confirm it survived. Sanitizer behavior can vary by
instance and version — don't assume it always keeps (or always strips) inline
styles without checking once.

**Publish state.** New pages default to `"published": false` unless the user
explicitly says this content can be published (Safety Rule 2). This default
does *not* carry over to the overwrite/merge path for an existing page — see
below.

**Default title**, when the user hasn't given one:
1. Look for the first `<h1>` in the generated HTML; use its text content
   (tags stripped, whitespace collapsed and trimmed) as the title.
2. If there's no `<h1>`, use the first `<h2>` the same way.
3. If there's no heading at all, fall back to `Untitled page (<local date and
   time>)`, e.g. `Untitled page (2026-07-07 14:33)`.
4. Truncate a derived title to ~120 characters (with an ellipsis) if the
   heading text is unusually long — it becomes the slug forever (see above),
   and long slugs are awkward in navigation and links.
5. Show the derived title to the user as part of the normal pre-write preview
   so they can override it *before* creation, not after — the slug is frozen at
   creation and does not follow later title edits.

**Checking whether the page already exists** (do this before create):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages --all --param "search_term=<title>"
```

`search_term` is fuzzy — a non-empty result is not automatically a collision.
Compare returned titles case-insensitively/trimmed for an exact match. No
exact match: create it (see Create, above). Exact match: this is the
existing-page path — go to "Overwrite vs. merge".

When generating a new page as part of a series (e.g. several related unit
pages), check `./.canvas-cache/<course_id>/` first for cached pages from
earlier in the series — reuse their structure, style, and content as a
starting point instead of re-deriving everything from scratch.

## Overwrite vs. merge (existing pages)

Triggering a page write against a slug that already exists always requires
asking the user which of the two paths below to take (Safety Rule 6) — even
mid-batch, even when the broader task was framed as autonomous.

1. Ask the user: overwrite, or merge with the live content? Show them the
   existing page's slug/`html_url` (and a short summary of its current
   content) so they're deciding with real information, not blind.
2. **Overwrite** — replace `body` entirely with the newly generated body via
   PUT, per Update above. Do **not** include `published` in the payload
   unless the user explicitly wants to change the live page's publish state.
   Omitting it leaves Canvas's existing value untouched; defaulting it to
   `false` here (per Safety Rule 2's *new*-content default) would silently
   unpublish a live page — a distinct destructive action needing its own
   confirmation (Safety Rule 1).
3. **Merge** — this is judgment at generation time, not a mechanical diff:
   - Fetch the live body fresh: `GET /courses/:course/pages/<slug>`. Never
     rely on the local cache for this side of the merge, even if a cache
     entry exists for this slug — it may be stale.
   - Read both the live body and the newly generated body.
   - Produce one reconciled HTML body: match sections by heading where
     reasonable, keep live content the new generation doesn't supersede,
     fold in the new material.
   - Show the merged result to the user and get explicit confirmation before
     writing anything.
   - PUT the confirmed body. Same rule as overwrite: omit `published` unless
     the user explicitly wants it changed.
4. **Staleness signal:** if a local cache entry exists for this slug, compare
   its `content_hash` (see "Local page cache") to a sha256 of the
   freshly-fetched live body. A mismatch means the live page changed since it
   was last cached — mention it to the user; it doesn't change the process
   (still fetch-live, reconcile, confirm) but is useful context.
5. Either path: after a successful PUT, cache the result (below).

## Local page cache

Every successful create/update through this capability is cached locally so
later work in the same project can build on real, current content instead of
re-deriving it from memory or re-fetching it.

- Location: `./.canvas-cache/<course_id>/<slug>.html` and
  `./.canvas-cache/<course_id>/<slug>.json`, relative to the current working
  directory (the user's project, not the plugin's directory).
- Written by piping the API response through `cache_pages.py`:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
      post /courses/:course/pages --json '...' --live \
    | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cache_pages.py --course 326
  ```
- `cache_pages.py` writes only to local disk and never calls Canvas, so it
  takes no `--live`; `--dry-run` previews what would be written (slugs, paths,
  byte counts, hashes) without touching disk.
- `.html`: the exact body Canvas stored (i.e. what the response actually
  contains, post-sanitization), byte for byte.
- `.json` sidecar: `page_id`, `url` (slug), `title`, `published`,
  `updated_at` (Canvas's own timestamp), `html_url`, `content_hash`
  (`sha256:<hex>` of the `.html` file), `cached_at` (local wall-clock ISO 8601
  timestamp of the cache write), `course_id`.
- The hash serves two purposes: detecting drift between the cache and the
  live page before a merge (above), and skipping redundant writes when
  regenerated content hashes identically to what's already cached.
- The cache is a convenience index, never a source of truth for whether a
  page exists or what it currently says. Always confirm against a live GET.
- **`.canvas-cache/` must be gitignored.** Page bodies themselves contain
  nothing secret, but the same directory holds downloaded student submissions
  and the course-reports snapshots, which are student records. The rule is one
  rule for the whole directory: see "Student data on disk" in the plugin
  README. Check `.gitignore` before the first write and add the entry if it is
  missing.

## Bulk-caching all pages in a course

On demand only — a separate operation from the per-write caching above, for
mirroring every page in the course locally, not just ones this capability
touched.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages --all --param "include[]=body" \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cache_pages.py --course 326
```

- `include[]=body` is required — the plain list omits `body` (see List/read
  above), and `cache_pages.py` has nothing to write without it. Objects
  missing `body` are skipped with a reason, not treated as fatal.
- Slow on large courses, same as the existing list-endpoint gotcha; warn the
  user before running it on a course with many pages.
- `cache_pages.py` accepts either a single page object or an array, so the
  same script backs both this and the per-write path above, and `--input-file`
  reads a saved JSON file instead of stdin.
- `--course-id` works instead of `--course` when there is no course folder;
  `--cache-dir` defaults to `./.canvas-cache`.
