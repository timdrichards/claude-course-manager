# Rendering a unit for Canvas

Canvas strips `<style>`, `<link>`, and `<script>` from a page body. Only inline `style="..."`
attributes survive, so a unit page has to arrive with its styling already applied to every element.
`render_html.py` converts the Markdown, inlines a stylesheet over the result, and then checks its
own output for the tags Canvas would have removed.

The Markdown is the source. The HTML is a build product, regenerated whenever the lesson changes.

## Dependencies

```bash
pip install markdown premailer pygments
```

The only part of this plugin that needs packages beyond the standard library, along with the
Piazza and Gradescope clients. Skip `pygments` only if every render passes `--no-highlight`.

## Rendering

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py course/units/09-idempotency
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py unit.md --css course/theme.css
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py unit.md --code-style dracula
```

Point it at a unit folder and it renders the lesson beside it. It takes `unit.md` when there is
one, and otherwise the folder's single Markdown file, so a course whose lessons are called `12.md`
works without arguments. A folder with several Markdown files says so rather than guessing. Point
it at a file and it renders that file.

With no `--css` it inlines `${CLAUDE_PLUGIN_ROOT}/assets/unit.css`: system font stack, a 760px
measure, a dark code container, styled tables and blockquotes. With `--css` the given stylesheet is
used in full and the bundled one is not merged underneath it.

A custom stylesheet has to stick to plain selectors. premailer drops `:hover`, media queries, and
pseudo-elements rather than inlining them, because an inline-only document has nowhere to put them.
It drops them without complaining, which is why the script checks the output afterwards.

## Code highlighting

Highlighting happens at render time, through Pygments in `noclasses` mode, which writes each
token's color as an inline style on its own span. This is the only kind that survives: Prism and
highlight.js both need a script and a stylesheet, and both are what Canvas removes, so a page
relying on them ships monochrome.

- **Fence every block with a language.** ` ```js `, ` ```python `. A bare fence still renders, in
  one color, and `units.py check` reports it.
- `--code-style` takes any Pygments style. It defaults to `github-dark` to match the bundled
  stylesheet's dark code container. A light style is dark text inside a dark box; `pygmentize -L
  styles` lists the rest.
- Code renders at body size rather than shrunken, in both inline and block form.

## What the script verifies

Two invariants, checked on every run rather than left for someone to remember:

1. **No `<style>`, `<link>`, or `<script>` in the output.** A match means the stylesheet had a rule
   premailer could not inline. The script exits 1 and names the tags. The file is still written, so
   the problem can be looked at, and it says plainly that what it wrote is not fit to post.
2. **A first `<h1>` or `<h2>` survived.** The Canvas page workflow derives a page title from that
   element, so a render that lost it produces a page named something nobody chose.

## Handing it to Canvas

Do not post from here. The canvas skill already owns the page lifecycle, and it handles the parts
that matter: the existence check, the overwrite or merge confirmation, the local cache, and the
write gate that keeps a dry run from becoming a live edit by accident. Read
`${CLAUDE_PLUGIN_ROOT}/skills/canvas/references/pages.md`.

Use the rendered file's contents as the page body, then record the page in `unit.json`:

```json
"canvas": {"page_url": "unit-9-idempotency", "page_id": 4471}
```

and set `status` to `published`. Without that record the next render creates a second page with the
same title, and students find both.

The first time a course posts a unit to a given Canvas instance, do the round trip once: create the
page, fetch it back, and confirm the inline styles survived the sanitizer. Instances differ in what
they allow, and finding out on unit 9 is worse than finding out on unit 1.
