#!/usr/bin/env python3
"""
deck_check.py: structural checks for a single-file reveal.js lecture deck.

Every rule here corresponds to a way a deck has actually shipped broken. The
expensive ones are silent: a dark theme that renders washed out because reveal's
own stylesheet hardcodes a white wrapper, an auto-animate pair that quietly does
not animate, code set at a size nobody past row ten can read. None of these raise
an error in a browser. All of them are visible in the file.

Offline by default, so it can run in CI and on a plane. Pass --check-urls to
actually resolve the CDN references over the network.

Usage:
    deck_check.py deck.html
    deck_check.py deck.html --check-urls
    deck_check.py deck.html --json
    deck_check.py *.html --quiet
    deck_check.py --self-test

Exit codes: 0 clean or warnings only, 1 something needs fixing, 2 bad input.
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Floors are in source pixels, before reveal's scale factor. A 1050x660 deck on
# a 1080p projector scales by about 1.55, so 20px of source code text lands near
# 31px on the wall. Below these numbers a lecture hall starts losing people.
BASE_FONT_FLOOR = 28
CODE_FONT_FLOOR = 18
DECK_HEIGHT_CEILING = 700
CODE_LINE_CEILING = 14

CDN_RE = re.compile(r"""["']((?:https?:)?//[^"'\s>]+)["']""")
REVEAL_VER_RE = re.compile(r"/reveal\.js/(\d+\.\d+\.\d+)/")

# Reveal 3 and 4 paths that 404 or no-op against 5.x. These arrive by copying a
# stale example, which is most of the reveal boilerplate on the web.
LEGACY = [
    (r"print/pdf(?:\.min)?\.css", "print/pdf.css was removed in reveal 5; print styles are "
                                  "compiled into reveal.min.css"),
    (r"css/reveal(?:\.min)?\.css", "css/reveal.css is a reveal 3 path"),
    (r"(?<!\.)\bjs/reveal(?:\.min)?\.js", "js/reveal.js is a reveal 3 path"),
    (r"lib/js/head\.min\.js", "head.min.js was dropped after reveal 3"),
]


class DeckParser(HTMLParser):
    """Collect the structure the checks need: sections, their data-ids, notes,
    code blocks, and every src/href in the document."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []          # {auto, ids, dup_ids, parent, index}
        self._open = []             # stack of indices into self.sections
        self.notes = 0
        self.code_langs = []
        self.links = []             # (tag, url)
        self.title = None
        self._in_title = False
        self._in_skip = 0           # inside script/style
        self._in_code = 0           # inside pre/code
        self._in_notes = 0
        self.visible = []           # visible slide prose, code and script removed
        self.pre_blocks = []        # text of each code block
        self._cur_pre = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._in_skip += 1
        if tag == "title":
            self._in_title = True
        if tag in ("pre", "code"):
            self._in_code += 1
            if tag == "pre":
                self._cur_pre = []
        if tag == "aside" and "notes" in (a.get("class") or ""):
            self.notes += 1
            self._in_notes += 1
        if tag == "code":
            cls = a.get("class") or ""
            m = re.search(r"language-([\w+-]+)", cls)
            if m:
                self.code_langs.append(m.group(1))
        # preconnect and dns-prefetch name an origin to warm up, not a resource to
        # fetch. HEADing one returns 404 from most CDNs, and a checker that reports
        # that gets the hint deleted, which is a small real loss for a false alarm.
        rel = (a.get("rel") or "").lower()
        hint_only = tag == "link" and any(r in rel for r in ("preconnect", "dns-prefetch"))
        for key in ("src", "href"):
            if key in a and a[key]:
                self.links.append((tag, a[key], hint_only))
        if tag == "section":
            parent = self._open[-1] if self._open else None
            self.sections.append({
                "auto": "data-auto-animate" in a,
                "restart": "data-auto-animate-restart" in a,
                "ids": [], "dup_ids": [], "parent": parent,
                "line": self.getpos()[0],
            })
            self._open.append(len(self.sections) - 1)
        if "data-id" in a and self._open:
            sec = self.sections[self._open[-1]]
            if a["data-id"] in sec["ids"]:
                sec["dup_ids"].append(a["data-id"])
            sec["ids"].append(a["data-id"])

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._in_skip:
            self._in_skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in ("pre", "code") and self._in_code:
            self._in_code -= 1
            if tag == "pre" and self._cur_pre is not None:
                self.pre_blocks.append("".join(self._cur_pre))
                self._cur_pre = None
        if tag == "aside" and self._in_notes:
            self._in_notes -= 1
        if tag == "section" and self._open:
            self._open.pop()

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        if self._cur_pre is not None:
            self._cur_pre.append(data)
        if self._in_skip or self._in_code:
            return
        if data.strip():
            self.visible.append((self.getpos()[0], data))


def find(rx, text, flags=re.I):
    return [m for m in re.finditer(rx, text, flags)]


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def check_deck(text, want_urls=False):
    p = DeckParser()
    p.feed(text)
    out = []

    def add(cid, sev, what, fix, lines=None, detail=None):
        out.append({"id": cid, "severity": sev, "what": what, "fix": fix,
                    "lines": sorted(set(lines or []))[:10],
                    "detail": detail or []})

    scripts = "\n".join(m.group(1) for m in
                        find(r"<script\b[^>]*>(.*?)</script>", text, re.I | re.S))
    styles = "\n".join(m.group(1) for m in
                       find(r"<style\b[^>]*>(.*?)</style>", text, re.I | re.S))
    # Blank CSS comments, preserving newlines so line numbers stay true. Without
    # this a deck that only mentions .reveal-viewport in a comment reads as having
    # the override, which is precisely the deck most likely to be missing it.
    styles = re.sub(r"/\*.*?\*/",
                    lambda m: "".join("\n" if c == "\n" else " " for c in m.group(0)),
                    styles, flags=re.S)

    # ---------------------------------------------------------- reveal is present
    has_reveal = bool(find(r"reveal(?:\.min)?\.js", text))
    has_init = bool(find(r"Reveal\s*\.\s*initialize", text))
    if not (has_reveal or has_init):
        add("not-a-deck", "fail",
            "No reveal.js reference and no Reveal.initialize call.",
            "This does not look like a reveal deck. Check the file.")
        return {"findings": out, "stats": {}}

    # ------------------------------------------------- the white viewport wrapper
    # reveal.min.css sets .reveal-viewport{background-color:#fff;color:#000}. It
    # is core CSS, not a theme, so styling only body and .reveal leaves a white
    # sheet behind a dark deck and light text renders washed out.
    vp = find(r"\.reveal-viewport\b[^{}]*\{([^}]*)\}", styles)
    if not vp:
        add("viewport-override", "fail",
            "No .reveal-viewport rule.",
            "reveal.min.css hardcodes this wrapper to background #fff and color #000. "
            "Add:  .reveal-viewport { background-color: var(--bg) !important; "
            "color: var(--text) !important; }")
    else:
        body = " ".join(m.group(1) for m in vp)
        if not re.search(r"background(-color)?\s*:", body, re.I):
            add("viewport-override", "fail",
                "A .reveal-viewport rule exists but sets no background.",
                "Set background-color on it, with !important, or reveal's own white wins.")
        elif "!important" not in body:
            add("viewport-important", "warn",
                "The .reveal-viewport background is set without !important.",
                "reveal.min.css may load after the inline style depending on ordering. "
                "Use !important so the override is not load-order dependent.")

    # ------------------------------------------------------------- legacy paths
    for rx, why in LEGACY:
        hits = find(rx, text)
        if hits:
            add("legacy-reveal-path", "fail", why,
                "This came from a reveal 3 or 4 example. Use the reveal 5 layout.",
                [line_of(text, m.start()) for m in hits])
    if find(r"\bdependencies\s*:", scripts):
        add("legacy-dependencies", "fail",
            "Reveal.initialize uses `dependencies:`.",
            "Reveal 5 takes `plugins: [RevealHighlight, RevealNotes]` with the plugin "
            "scripts loaded as ordinary <script> tags.")

    # ---------------------------------------------------------- version coherence
    versions = sorted({m.group(1) for m in REVEAL_VER_RE.finditer(text)})
    if len(versions) > 1:
        add("version-mix", "fail",
            f"Reveal files are loaded from {len(versions)} versions: {', '.join(versions)}.",
            "Pin every reveal file, core and plugins, to one version.")

    # ------------------------------------------------------------- self-contained
    external = []
    for tag, url, _hint in p.links:
        u = url.strip()
        if u.startswith(("http://", "https://", "//", "data:", "#", "mailto:")):
            continue
        external.append(f"<{tag}> {u}")
    if external:
        add("not-self-contained", "fail",
            f"{len(external)} reference(s) to local files.",
            "A deck must be one file that survives being emailed. Inline the CSS and JS, "
            "and embed images as data: URLs.", detail=external[:8])

    # ------------------------------------------------------------ browser storage
    st = find(r"\b(?:local|session)Storage\b", scripts)
    if st:
        add("browser-storage", "fail",
            "The deck uses localStorage or sessionStorage.",
            "Keep demo state in ordinary variables. Browser storage is unavailable in "
            "some contexts the deck will be opened in.")

    # ---------------------------------------------------------------- deck sizing
    init = find(r"Reveal\s*\.\s*initialize\s*\(\s*\{(.*?)\}\s*\)", scripts, re.S)
    cfg = init[0].group(1) if init else ""
    w = re.search(r"\bwidth\s*:\s*(\d+)", cfg)
    h = re.search(r"\bheight\s*:\s*(\d+)", cfg)
    if not (w and h):
        add("deck-size-default", "warn",
            "Reveal.initialize does not set both width and height.",
            "Reveal defaults to 960x700. Set them explicitly. On a widescreen projector the "
            "height is what sets the scale factor, so a height near 620 to 680 buys real "
            "legibility that changing the width alone does not.")
    elif int(h.group(1)) > DECK_HEIGHT_CEILING:
        add("deck-too-tall", "warn",
            f"Deck height is {h.group(1)}, above {DECK_HEIGHT_CEILING}.",
            "Scale is min(screen_w/deck_w, screen_h/deck_h), so on a 16:9 screen the height "
            "is the binding term. A taller deck renders smaller text.")

    # --------------------------------------------------------------- type sizing
    base = None
    for m in find(r"\.reveal\s*\{([^}]*)\}", styles):
        fs = re.search(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", m.group(1))
        if fs:
            base = float(fs.group(1))
    if base is None:
        add("base-font-unset", "warn",
            "No explicit px font-size on .reveal.",
            f"Set one so the floors are checkable. {BASE_FONT_FLOOR}px or more is the "
            "target for a lecture hall.")
    elif base < BASE_FONT_FLOOR:
        add("base-font-small", "warn",
            f"Base font on .reveal is {base:g}px, below the {BASE_FONT_FLOOR}px floor.",
            "Reveal's scale factor alone does not rescue sizes tuned on a laptop.")

    for m in find(r"\.reveal\s+pre(?:\s+code)?\s*\{([^}]*)\}", styles):
        em = re.search(r"font-size\s*:\s*(\d+(?:\.\d+)?)em", m.group(1))
        px = re.search(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", m.group(1))
        eff = float(px.group(1)) if px else (float(em.group(1)) * (base or 32) if em else None)
        if eff is not None and eff < CODE_FONT_FLOOR:
            add("code-font-small", "warn",
                f"Code renders at about {eff:.0f}px of source size, below the "
                f"{CODE_FONT_FLOOR}px floor.",
                "Code is the densest thing on a slide and the thing students most need to "
                "read exactly. Show fewer lines rather than smaller type.")

    long_blocks = [i for i, b in enumerate(p.pre_blocks)
                   if len([l for l in b.strip().splitlines() if l.strip()]) > CODE_LINE_CEILING]
    if long_blocks:
        add("code-block-long", "warn",
            f"{len(long_blocks)} code block(s) run past {CODE_LINE_CEILING} lines.",
            "Split across an auto-animate pair, or walk it with data-line-numbers steps.")

    # --------------------------------------------------------- auto-animate pairs
    groups = {}
    for i, s in enumerate(p.sections):
        groups.setdefault(s["parent"], []).append(i)

    unpaired, no_shared, dups = [], [], []
    for _, sibs in groups.items():
        for pos, i in enumerate(sibs):
            s = p.sections[i]
            if s["dup_ids"]:
                dups.append((s["line"], sorted(set(s["dup_ids"]))))
            if not s["auto"]:
                continue
            prev = p.sections[sibs[pos - 1]] if pos > 0 else None
            nxt = p.sections[sibs[pos + 1]] if pos + 1 < len(sibs) else None
            neighbours = [n for n in (prev, nxt) if n and n["auto"]]
            if not neighbours:
                unpaired.append(s["line"])
                continue
            if s["ids"] and not any(set(s["ids"]) & set(n["ids"]) for n in neighbours):
                no_shared.append(s["line"])

    if unpaired:
        add("auto-animate-orphan", "fail",
            f"{len(unpaired)} section(s) marked data-auto-animate with no adjacent "
            "auto-animate sibling.",
            "Auto-animate needs two consecutive sections both carrying the attribute. "
            "A lone one is a plain slide and animates nothing, silently.", unpaired)
    if no_shared:
        add("auto-animate-no-match", "fail",
            f"{len(no_shared)} auto-animate section(s) share no data-id with a neighbour.",
            "Nothing pairs, so the whole slide cross-fades instead of morphing. Put matching "
            "data-id attributes on the elements that should animate into each other.", no_shared)
    if dups:
        add("auto-animate-dup-id", "warn",
            f"{len(dups)} section(s) reuse a data-id internally.",
            "Reveal pairs duplicates in document order, so this works until an edit reorders "
            "something and it pairs the wrong two elements. Keep ids unique per section.",
            [d[0] for d in dups], [f"line {l}: {', '.join(ids)}" for l, ids in dups])

    # ------------------------------------------------------------------- plugins
    plugins = re.search(r"plugins\s*:\s*\[([^\]]*)\]", cfg or scripts)
    plist = plugins.group(1) if plugins else ""
    if p.notes == 0:
        add("no-speaker-notes", "warn",
            "No <aside class=\"notes\"> anywhere in the deck.",
            "Discussion prompts and interactive slides are close to useless without them. "
            "They open with S and never reach the projector.")
    elif "RevealNotes" not in plist:
        add("notes-plugin-missing", "fail",
            f"{p.notes} speaker note(s) present but RevealNotes is not in plugins.",
            "Load plugin/notes/notes.min.js and add RevealNotes to the plugins array, or "
            "pressing S opens an empty window.")
    if p.code_langs and "RevealHighlight" not in plist:
        add("highlight-plugin-missing", "fail",
            "Code blocks declare a language but RevealHighlight is not in plugins.",
            "Load plugin/highlight/highlight.min.js and add RevealHighlight, or the code "
            "renders unhighlighted.")

    # --------------------------------------------------------------- interactive
    interactive = bool(find(r"addEventListener\s*\(\s*['\"](?:click|input|change|keydown)",
                            scripts)) or bool(find(r"\bon(?:click|input|change)\s*=", text))
    if not interactive:
        add("not-interactive", "warn",
            "No click, input, or change handler anywhere in the deck.",
            "At least one slide should compute something live. That capability is the reason "
            "to build the deck in a browser rather than in PowerPoint.")

    if find(r"setInterval\s*\(", scripts) and not find(r"clearInterval\s*\(", scripts):
        add("timer-never-cleared", "warn",
            "setInterval with no matching clearInterval.",
            "A timer started on slide four is still running at the end of the lecture. "
            "Clear it on Reveal.on('slidechanged', ...).")

    # ------------------------------------------------------- house style on slides
    visible = "\n".join(t for _, t in p.visible)
    for cid, rx, what, fix in [
        ("em-dash", r"—", "An em dash in visible slide text.",
         "House style. Use a comma, a period, or a semicolon. Em dashes survive in decks "
         "longer than anywhere else because nobody proofreads a slide."),
        ("curly-quote", r"[“”‘’]", "A curly quote or apostrophe in slide text.",
         "Use straight quotes. These mark text as pasted from a chat window."),
        ("todo-marker", r"\b(?:TODO|TBD|FIXME|XXX)\b", "A TODO or TBD marker on a slide.",
         "Resolve it, or mark it [CHECK: ...] so it is deliberate and visible."),
    ]:
        flags = re.I if cid == "em-dash" else (0 if cid == "todo-marker" else re.I)
        hits = [(ln, t) for ln, t in p.visible if re.search(rx, t, flags)]
        if hits:
            add(cid, "fail", f"{len(hits)} instance(s). {what}", fix,
                [ln for ln, _ in hits],
                [t.strip()[:70] for _, t in hits[:3]])

    if not (p.title or "").strip():
        add("no-title", "warn", "The document has no <title>.",
            "It becomes the browser tab and the PDF filename. Use the course number, "
            "the lecture number, and the topic.")

    # ------------------------------------------------------------------ the network
    if want_urls:
        import urllib.error
        import urllib.request
        urls = sorted({u for _, u, hint in p.links
                       if u.startswith(("http://", "https://")) and not hint})
        bad = []
        for u in urls:
            try:
                req = urllib.request.Request(u, method="HEAD",
                                             headers={"User-Agent": "deck_check"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    if r.status >= 400:
                        bad.append(f"{r.status} {u}")
            except urllib.error.HTTPError as e:
                bad.append(f"{e.code} {u}")
            except Exception as e:                       # noqa: BLE001
                bad.append(f"unreachable ({e.__class__.__name__}) {u}")
        if bad:
            add("cdn-unreachable", "fail",
                f"{len(bad)} of {len(urls)} external reference(s) did not resolve.",
                "cdnjs prunes versions. Pin one that returns 200.", detail=bad[:8])

    order = {"fail": 0, "warn": 1}
    out.sort(key=lambda f: order.get(f["severity"], 9))
    stats = {
        "sections": len(p.sections),
        "auto_animate_sections": sum(1 for s in p.sections if s["auto"]),
        "speaker_notes": p.notes,
        "code_blocks": len(p.pre_blocks),
        "reveal_versions": versions,
        "base_font_px": base,
        "deck_size": f"{w.group(1)}x{h.group(1)}" if (w and h) else "default 960x700",
    }
    return {"findings": out, "stats": stats}


LABEL = {"fail": "FAIL", "warn": "WARN"}


def report(name, result, quiet=False):
    lines = [name, "=" * len(name)]
    fs = result["findings"]
    if not fs:
        lines.append("  Nothing flagged.")
    for f in fs:
        loc = ""
        if f["lines"]:
            loc = "  line " + ", ".join(str(l) for l in f["lines"][:8])
        lines.append(f"\n  [{LABEL[f['severity']]}] {f['id']}{loc}")
        lines.append(f"    {f['what']}")
        for d in f["detail"][:5]:
            lines.append(f"      > {d}")
        lines.append(f"    {f['fix']}")
    if not quiet and result["stats"]:
        s = result["stats"]
        base = f"{s['base_font_px']:g}px" if s["base_font_px"] else "unset"
        vers = ", ".join(s["reveal_versions"]) or "not detected"
        lines.append("")
        lines.append(f"  {s['sections']} sections, {s['auto_animate_sections']} auto-animate, "
                     f"{s['code_blocks']} code blocks, {s['speaker_notes']} speaker notes.")
        lines.append(f"  Deck {s['deck_size']}, base font {base}, reveal {vers}.")
    return "\n".join(lines)


# ------------------------------------------------------------------- self-test

BAD = """<html><head><style>
body { background: #111; } .reveal { color: #eee; font-size: 20px; }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/print/pdf.min.css">
<link rel="stylesheet" href="./local.css">
</head><body><div class="reveal"><div class="slides">
<section data-auto-animate><h2 data-id="a">One</h2><p>A dash — here</p></section>
<section><h2 data-id="a">Two</h2></section>
<section data-auto-animate><p data-id="q">Q</p></section>
<section data-auto-animate><p data-id="z">Z</p></section>
<section><code class="language-js">x</code><p>TODO fix this</p></section>
</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.2.1/reveal.min.js"></script>
<script>localStorage.setItem('a', 1);
Reveal.initialize({ dependencies: [] });</script>
</body></html>"""

GOOD = """<html><head><title>COMPSCI 426 . Lecture 7</title><style>
:root { --bg:#0b1a2b; --text:#e6eef7; }
.reveal-viewport { background-color: var(--bg) !important; color: var(--text) !important; }
.reveal { font-size: 32px; color: var(--text); }
.reveal pre { font-size: 0.62em; }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.css">
</head><body><div class="reveal"><div class="slides">
<section><h1>Caching</h1></section>
<section data-auto-animate><pre data-id="c"><code class="language-js">const a = 1;</code></pre></section>
<section data-auto-animate><pre data-id="c"><code class="language-js">const a = 2;</code></pre></section>
<section><button id="go">run</button><aside class="notes">Ask before clicking.</aside></section>
</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/highlight/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/notes/notes.min.js"></script>
<script>
Reveal.initialize({ width: 1050, height: 660, plugins: [RevealHighlight, RevealNotes] });
document.getElementById('go').addEventListener('click', () => {});
</script>
</body></html>"""


def self_test():
    ok = True
    bad = {f["id"] for f in check_deck(BAD)["findings"]}
    want = {"viewport-override", "legacy-reveal-path", "legacy-dependencies", "version-mix",
            "not-self-contained", "browser-storage", "auto-animate-no-match", "em-dash",
            "todo-marker", "base-font-small", "highlight-plugin-missing", "no-speaker-notes",
            "deck-size-default", "not-interactive"}
    missing = want - bad
    if missing:
        ok = False
        print(f"FAIL: broken deck did not trigger {sorted(missing)}")
    else:
        print(f"ok: broken deck triggered {len(bad)} checks")

    good = check_deck(GOOD)
    fails = [f["id"] for f in good["findings"] if f["severity"] == "fail"]
    if fails:
        ok = False
        print(f"FAIL: clean deck reported {fails}")
    else:
        print("ok: clean deck reported no failures")

    # The pairing check must not fire on a correctly paired deck, and must fire
    # on a lone auto-animate section. Both directions matter.
    lone = check_deck(GOOD.replace(
        '<section data-auto-animate><pre data-id="c"><code class="language-js">const a = 2;'
        '</code></pre></section>',
        '<section><pre data-id="c"><code class="language-js">const a = 2;</code></pre></section>'))
    if "auto-animate-orphan" not in {f["id"] for f in lone["findings"]}:
        ok = False
        print("FAIL: a lone auto-animate section was not caught")
    else:
        print("ok: lone auto-animate section caught")

    # A comment naming the override is not the override. This one shipped: the
    # regex matched inside /* ... */ and then read the next rule's braces.
    commented = check_deck(GOOD.replace(
        ".reveal-viewport { background-color: var(--bg) !important; "
        "color: var(--text) !important; }",
        "/* remember the .reveal-viewport override */"))
    if "viewport-override" not in {f["id"] for f in commented["findings"]}:
        ok = False
        print("FAIL: .reveal-viewport named only in a CSS comment counted as the override")
    else:
        print("ok: CSS comments do not satisfy the viewport check")

    print("\nSELF-TEST PASSED" if ok else "\nSELF-TEST FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Structural checks for a reveal.js deck.")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--check-urls", action="store_true",
                    help="Resolve external references over the network")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="Findings only, no summary line")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.files:
        ap.print_help()
        return 2

    results, rc = {}, 0
    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f"No such file: {f}", file=sys.stderr)
            return 2
        r = check_deck(path.read_text(errors="replace"), want_urls=args.check_urls)
        results[f] = r
        if any(x["severity"] == "fail" for x in r["findings"]):
            rc = 1

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n\n".join(report(f, results[f], args.quiet) for f in args.files))
        if rc:
            print("\nSomething above needs fixing before this deck is presented.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
