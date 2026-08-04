#!/usr/bin/env python3
"""
render_html.py: render a unit's Markdown to Canvas-ready HTML.

Canvas strips <style>, <link>, and <script> from page bodies. Only inline
style="..." attributes survive, so a page has to arrive with its styling already
inlined onto every element. This script converts the Markdown, inlines a
stylesheet over the result, and then checks its own output for the tags Canvas
would have removed, because a page that silently lost its formatting looks like
a page nobody proofread.

Code is highlighted at render time with Pygments in noclasses mode, which writes
each token's color as an inline style on its span. A runtime highlighter cannot
work here: Prism and highlight.js both need a script and a stylesheet, and both
are exactly what Canvas removes. Fence code with a language (```js, ```python)
so the right lexer is picked; an unlabeled block still renders, in one color.

Requires: pip install markdown premailer pygments

Usage:
    render_html.py course/units/09-idempotency          # renders unit.md
    render_html.py 09.md -o 09.html
    render_html.py unit.md --css course/theme.css
    render_html.py unit.md --code-style dracula
    render_html.py unit.md --no-highlight

Pick a dark --code-style to match the bundled stylesheet's dark code container
(github-dark, monokai, dracula, one-dark). A light style is dark text in a dark
box. `pygmentize -L styles` lists them.

A custom --css must stick to plain selectors. premailer drops :hover and media
queries rather than inlining them, since an inline-only document has nowhere to
put them.

Exit codes: 0 rendered and verified, 1 the output would not survive Canvas,
2 bad input or a missing dependency.
"""

import argparse
import os
import re
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSS = os.path.join(PLUGIN_ROOT, "assets", "unit.css")

STRIPPED_BY_CANVAS = re.compile(r"<\s*(style|link|script)\b", re.I)
FIRST_HEADING = re.compile(r"<h([12])\b[^>]*>(.*?)</h\1>", re.I | re.S)


def need(module, package, hint=""):
    try:
        return __import__(module)
    except ImportError:
        sys.exit(f"error: this needs the {package!r} package "
                 f"(pip install {package}){hint}")


def render(md_path, css_path, code_style="github-dark", highlight=True):
    markdown = need("markdown", "markdown")
    need("premailer", "premailer")
    from premailer import transform

    extensions = ["extra", "fenced_code", "tables"]
    configs = {}
    if highlight:
        need("pygments", "pygments", ", or pass --no-highlight")
        extensions.append("codehilite")
        configs["codehilite"] = {"noclasses": True, "pygments_style": code_style,
                                 "guess_lang": False}

    with open(md_path, encoding="utf-8") as fh:
        body = markdown.markdown(fh.read(), extensions=extensions,
                                 extension_configs=configs)
    with open(css_path, encoding="utf-8") as fh:
        css_text = fh.read()

    html = f'<html><head><meta charset="utf-8"></head><body>{body}</body></html>'
    return transform(html, css_text=css_text, disable_leftover_css=True,
                     disable_validation=True, remove_classes=True)


def verify(html):
    """The two invariants, checked here rather than left to a person to remember.

    The first is Canvas's sanitizer. The second is the page title: the Canvas
    page workflow derives a title from the first h1 or h2, so a render that lost
    that heading produces a page called something nobody chose.
    """
    problems = []
    leftover = sorted({m.group(1).lower() for m in STRIPPED_BY_CANVAS.finditer(html)})
    if leftover:
        problems.append(
            f"the output still contains <{'>, <'.join(leftover)}>. Canvas removes "
            f"these, so whatever they carried will be missing on the page. Usually "
            f"a stylesheet rule premailer could not inline, such as :hover or a "
            f"media query.")
    if not FIRST_HEADING.search(html):
        problems.append(
            "the output has no <h1> or <h2>. The Canvas page title is derived "
            "from the first one, so give the document a top-level heading.")
    return problems


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="A Markdown file, or a unit folder holding unit.md")
    ap.add_argument("--css", default=DEFAULT_CSS,
                    help="Stylesheet to inline (default: the bundled assets/unit.css)")
    ap.add_argument("--code-style", default="github-dark",
                    help="Pygments style for code (default: github-dark)")
    ap.add_argument("--no-highlight", action="store_true",
                    help="Plain code blocks, no Pygments")
    ap.add_argument("-o", "--output", help="Output path (default: alongside the source)")
    args = ap.parse_args()

    src = args.source
    if os.path.isdir(src):
        unit_md = os.path.join(src, "unit.md")
        if not os.path.isfile(unit_md):
            sys.exit(f"error: {src} has no unit.md")
        src = unit_md
    if not os.path.isfile(src):
        sys.exit(f"error: no such file: {src}")
    if not os.path.isfile(args.css):
        sys.exit(f"error: no such stylesheet: {args.css}")

    out = args.output or os.path.splitext(src)[0] + ".html"
    html = render(src, args.css, code_style=args.code_style,
                  highlight=not args.no_highlight)

    problems = verify(html)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(out)
    for p in problems:
        print(f"  FAIL {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
