# Editing a live syllabus page

The syllabus is a published page that students are reading right now. Every edit is a live edit.
This file is the discipline that keeps one from losing content.

---

## Fetch before you reason

Always pull the current page immediately before editing. Never work from a copy taken earlier in
the session, from the course profile's summary, or from memory.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages --all --param "search_term=syllabus"

python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/pages/<slug> > /tmp/syllabus-live.json
```

The list endpoint omits `body`; fetching a single page by slug is what returns it.

The reason for re-fetching is not theoretical. A syllabus edited from an hour-old copy reverts
whatever changed in between, and parallel work on the same course is normal. If real time has
passed, or anything else plausibly touched the course, fetch again.

**The slug is frozen at creation.** It derives from the title when the page is first made and
does not change when the title changes. A course whose page reads `326-su26-syllabus` keeps that
slug even after the title gains an emoji or the term rolls.

---

## Edit surgically

Prefer replacing the specific paragraph over regenerating the page.

Regeneration is how content disappears. A re-render silently strips syntax highlighting from code
blocks and silently drops embedded images unless the image map is passed through. Neither failure
raises an error; the page just comes back plainer than it went in, and nobody notices until a
student asks why the example lost its colors.

For a targeted change: extract `body`, replace the exact substring, and PUT the whole body back.
Verify the substring matched before writing. A replacement that silently matched nothing produces
a successful-looking PUT that changed nothing.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/pages/<slug> --json-file /tmp/syllabus-edit.json --live
```

Send only the fields you mean to change. **Omit `published` entirely** when editing an already
live page. Sending `"published": false` by default is how a live syllabus goes dark mid-term, and
Canvas leaves the existing value alone when the key is absent.

---

## The drift check

Before pushing an edit built from a local source rather than the fetched body, confirm the local
source and the live page still agree.

Render the local source unmodified, extract the text of both it and the live HTML, and compare
line for line. Only when they are identical should the intended edit be applied. If they differ,
the live page has changes the local source does not know about, and pushing would revert them.

This check is cheap and it is the one that catches the expensive mistake.

---

## Verify after every write

A write is not done when the request returns 200.

Fetch the page back and confirm: the intended change is present as an exact substring, `published`
is still what it was, the `<h1>` survived, images still resolve to real URLs, and no `<style>`,
`<link>`, or `<script>` tags remain. Canvas strips those three on save, so a surviving one means
the generated HTML was malformed in a way that will bite later.

Report the page's `html_url` so the instructor can click through and look at it.

---

## Styling

Canvas strips `<style>`, `<link>`, and `<script>`. All styling must be inline on the elements
themselves.

Courses usually settle on a page template: a wrapper div with a max width and centered margins, a
body font, a text color, an accent color on the `<h1>` underline, and a comfortable line height.
Match whatever the course's existing pages already do rather than introducing a new look on the
syllabus alone. Fetch a current page and read its markup to find the convention.

Where a course has more than one page style in play, they exist for different page families and
must not be mixed. Check which family the syllabus belongs to before restyling anything, and do
not "fix" a page whose style differs deliberately.

---

## Creating a syllabus page that does not exist yet

1. Draft in markdown and show it. Get approval on content before anything touches the LMS.
2. Convert to inline-styled HTML matching the course's page convention.
3. Create the page **unpublished** (`"published": false`).
4. Fetch it back, verify, and give the instructor the URL to look at.
5. Publish only when they say to.

New content defaults to unpublished. The exception is announcements, which are live on creation,
which is exactly why they need confirmation first.

---

## Publishing, and who does it

Publishing is student-visible. It needs explicit approval every time, and a previous approval is
not standing permission for the next one.

If an object turns out to be published and nothing in this session published it, the instructor
did it themselves. That is the normal case, not a bug. Do not revert it.

---

## The write gate

Every Canvas write in this plugin needs `--live` on the command and `"write_mode": "live"` in the
course's `.infra/canvas/config.json`. Without both, the command prints the request it would send
and stops.

Every write appends to `.infra/canvas/actions.log` with the previous value, so a reversal is
reconstructible:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 undo
```

For a page edit, the recorded before-value is the previous body. Keep that in mind before a large
replacement: the log is the only copy of what the page used to say.
