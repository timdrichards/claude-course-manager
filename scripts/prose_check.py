#!/usr/bin/env python3
"""
prose_check.py: flag writing that reads as machine-generated.

Every skill in this plugin drafts text that a student, a colleague, or a dean
will read. This script is the check that runs before any of it is handed over.

The tells come from Wikipedia's "Signs of AI writing" (WP:AISIGNS), which is the
most carefully assembled list in existence because the people who wrote it spend
their days cleaning up after the thing they are describing. Two of its own
warnings shape how this script behaves.

First: the signs are descriptive, not prescriptive. The guide says outright that
these are "observations, not rules," that "many elements of AI writing can be
found in editorials, blogs, or fan fiction," and, most importantly, that treating
the signs as the problem itself "could just make detection harder." So this
script reports and explains rather than rewrites, and most of what it reports is
density and co-occurrence rather than a single banned word. One "crucial" is
nothing. Nine of these words in four hundred is a paragraph nobody wrote.

Second: several things people confidently call AI tells are not. Perfect grammar,
formal or academic prose, hedging, transition words, and the Oxford comma are all
either explicitly listed as ineffective indicators or absent from the guide
entirely. This script does not flag them, and stripping them out of prose to
sound human is how writing ends up worse and no less synthetic.

The one place it is absolute is the character set. Em dashes, curly quotes, and
stray emoji are house style, not statistics, and they get flagged every time.

Usage:
    prose_check.py draft.md
    prose_check.py --stdin < draft.md
    prose_check.py --text "the paragraph to check"
    prose_check.py draft.md --json
    prose_check.py draft.md --quiet          # findings only, no positives
    prose_check.py --self-test

Exit codes: 0 clean or advisory only, 1 something needs fixing, 2 bad input.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# ------------------------------------------------------------------ vocabulary
#
# Wikipedia gates its list on external corpus studies. The number is how many
# independent academic sources documented the overuse, which is a decent proxy
# for how much weight one instance deserves. Words below are scored, never
# banned: the guide is explicit that "a word being overused by AI does not imply
# that its synonyms are also overused," so this list is taken literally.

AI_VOCAB = {
    "delve": 4, "delves": 4, "delving": 4,
    "intricate": 4, "intricacies": 4,
    "underscore": 4, "underscores": 4, "underscoring": 4,
    "crucial": 3, "showcase": 3, "showcases": 3, "showcasing": 3,
    "tapestry": 3,
    "align with": 2, "aligns with": 2, "aligning with": 2,
    "emphasizing": 2, "enhance": 2, "enhances": 2, "enhancing": 2,
    "fostering": 2, "foster": 2, "garner": 2, "garnered": 2,
    "meticulous": 2, "meticulously": 2, "pivotal": 2,
    "boasts": 1, "bolstered": 1, "enduring": 1, "interplay": 1,
    "testament": 1, "vibrant": 1, "valuable": 1,
    # In the guide's box but uncited or citation-needed. Kept at low weight.
    "robust": 1, "landscape": 1,
}

# "Additionally" counts only at the start of a sentence, per the guide.
SENTENCE_INITIAL = {"additionally"}

# ----------------------------------------------------------------- the patterns
#
# (id, severity, compiled regex, what it is, what to do instead)

def _p(pattern, flags=re.I):
    return re.compile(pattern, flags)


CHECKS = [
    # -------- character set. House style, not statistics. Always a finding.
    ("em-dash", "fix", _p(r"—"),
     "An em dash.",
     "Use a comma, a period, or a semicolon, whichever fits. Most sentences "
     "that reach for an em dash want a period."),

    ("curly-quote", "fix", _p(r"[“”‘’]"),
     "A curly quotation mark or apostrophe.",
     "Use straight quotes and apostrophes. These arrive from smart-quote "
     "substitution and mark text as pasted from a chat window."),

    ("emoji-heading", "fix",
     _p(r"^\s{0,3}#{1,6}\s*[\U0001F300-\U0001FAFF☀-➿]", re.M),
     "An emoji decorating a heading.",
     "Course title conventions may use a deliberate emoji prefix; a decorative "
     "one inside prose headings is a chatbot habit. Check house-style.md."),

    ("citation-artifact", "fix",
     _p(r"↩|【[^】]*†[^】]*】|citeturn\d||"),
     "A chatbot citation artifact.",
     "Remove it. These are interface markers, not content."),

    ("ai-residue", "fix",
     _p(r"as an AI language model|I(?:'m| am) (?:an AI|unable to browse)|"
        r"my (?:knowledge|training) (?:cut[- ]?off|data)|"
        r"as of my last (?:update|knowledge)|I cannot browse the internet"),
     "Assistant residue left in the text.",
     "Delete it. This should never reach a reader."),

    # TBD/TODO are case-sensitive on purpose: "todo list" is ordinary English,
    # "TODO" left in a draft is not. Same for bracketed instructions, which must
    # look like an instruction rather than a checkbox or a citation.
    ("placeholder", "fix",
     _p(r"\[(?:insert|add your|your \w+ here|company name|topic name)\b[^\]]*\]|"
        r"\blorem ipsum\b", re.I),
     "Placeholder text.",
     "Fill it in, or mark it `[CHECK: ...]` so it is deliberate and visible."),

    ("todo-marker", "fix", _p(r"\b(?:TODO|TBD|FIXME|XXX)\b", 0),
     "A TODO or TBD marker.",
     "Resolve it, or convert it to `[CHECK: ...]`, which is the convention this "
     "plugin uses for a gap the instructor must fill."),

    # -------- strong structural tells
    ("negative-parallelism", "strong",
     _p(r"\b(?:not (?:just|only|merely|simply)\b[^.!?\n]{2,80}?\b(?:but|it'?s)\b|"
        r"(?:it|this|that)(?:'s| is| was) not (?:about )?[^.!?\n]{2,60}?,\s*(?:it|it'?s)\b)"),
     "A negative parallelism (\"not just X, but Y\" / \"It's not X, it's Y\").",
     "State the thing directly. The construction implies you are correcting a "
     "misconception the reader never had."),

    ("significance-puffery", "strong",
     _p(r"\b(?:stands as|serves as|is) a (?:testament|reminder|symbol)\b|"
        r"\bplays? an? (?:crucial|pivotal|vital|significant|key) role\b|"
        r"\b(?:underscores|highlights) (?:its|the) (?:importance|significance)\b|"
        r"\b(?:enduring|lasting) legacy\b|\bindelible mark\b|\bwatershed moment\b|"
        r"\breflects broader\b|\bevolving landscape\b|\brich (?:cultural )?"
        r"(?:heritage|tapestry|history)\b"),
     "Canned significance language.",
     "Say what the thing does, not what it represents. If its importance needs "
     "asserting, the specifics were left out."),

    ("superficial-ing", "strong",
     _p(r",\s+(?:highlighting|underscoring|emphasizing|reflecting|symbolizing|"
        r"showcasing|ensuring|contributing to|cultivating|fostering|enhancing|"
        r"demonstrating|solidifying|cementing|reinforcing|illustrating)\b"),
     "A trailing \"-ing\" clause interpreting the sentence it hangs off.",
     "Cut it, or make it a real claim in its own sentence with a source. These "
     "add the appearance of analysis and no information."),

    ("challenges-formula", "strong",
     _p(r"\bdespite (?:its|these|those|the) [^.\n]{0,40}\b(?:challenges|"
        r"limitations|obstacles|setbacks)\b|"
        r"^\s{0,3}#{1,6}\s*(?:challenges and (?:future|legacy|opportunities)|"
        r"future (?:prospects|outlook|directions))\s*$", re.I | re.M),
     "The \"Despite these challenges\" / \"Future Prospects\" formula.",
     "This is a shape, not a thought. Say the specific difficulty and what is "
     "being done, or cut the section."),

    ("summary-sentence", "strong",
     _p(r"^\s*(?:in (?:summary|conclusion)|overall|to sum(?: it)? up|"
        r"in closing)\b[,:]", re.I | re.M),
     "A summary or conclusion restating what was just said.",
     "Delete it. A reader who got this far does not need the recap."),

    ("vague-attribution", "strong",
     _p(r"\b(?:some |many |several |most )?(?:critics|observers|experts|"
        r"scholars|researchers|analysts|commentators)\s+(?:argue|note|have noted|"
        r"say|contend|suggest|believe|point out|have cited)\b|"
        r"\bindustry (?:reports|publications|observers)\b|"
        r"\b(?:studies|research) (?:show|suggest|indicate)s?\b(?![^.\n]{0,60}\()"),
     "An opinion attributed to an unnamed authority.",
     "Name the source or drop the claim. In course material an invented "
     "consensus is worse than no claim at all."),

    ("copula-avoidance", "review",
     _p(r"\b(?:serves as|stands as|functions as|operates as|acts as) an?\b|"
        r"\bboasts an?\b|\bholds the distinction of\b"),
     "A dressed-up replacement for \"is\" or \"has\".",
     "Use \"is\" or \"has\". The plain copula is one of the documented signs of "
     "human writing."),

    ("promo-adjective", "review",
     _p(r"\b(?:nestled|breathtaking|must-(?:visit|see)|stunning natural beauty|"
        r"a diverse array of|in the heart of|renowned for|groundbreaking|"
        r"cutting-edge|game[- ]?chang(?:er|ing)|seamless(?:ly)?|"
        r"unlock(?:ing)? the (?:power|potential)|embark on)\b"),
     "Travel-brochure or sales vocabulary.",
     "Cut it or replace it with the specific fact it is standing in for."),

    ("notability-canned", "review",
     _p(r"\b(?:independent coverage|trade publications|profiled in|"
        r"active social media presence|maintains a strong (?:digital|online) presence|"
        r"prominent media outlets)\b"),
     "Canned notability language.",
     "This wording is idiosyncratic to AI text. Say what was actually "
     "published, and where."),
]

# Human-writing signals. Presence is reassuring, absence is not damning.
HUMAN_SIGNALS = [
    ("plain copula", _p(r"\b(?:there (?:is|are|was|were)|it (?:is|was|has))\b")),
    ("plain verb", _p(r"\b(?:wrote|moved|used|tried|died|made|got|kept|ran)\b")),
    ("definite claim", _p(r"\b(?:one of the (?:best|worst|first)|is the only|"
                          r"was the first|never|always)\b")),
    ("hedge", _p(r"\b(?:perhaps|probably|tends to|roughly|about|mostly|"
                 r"usually|often)\b")),
    ("wordy human construction", _p(r"\b(?:as a result of|in order to|"
                                    r"all of the|a part of|the fact that)\b")),
]


# -------------------------------------------------------------------- utilities

EXEMPT_MARKER = re.compile(r"<!--\s*prose-check:\s*reference\s*-->")
OFF_ON = re.compile(r"<!--\s*prose-check:\s*off\s*-->.*?<!--\s*prose-check:\s*on\s*-->", re.S)


def is_exempt(text):
    """A document that catalogues these tells has to quote them. Marking such a
    file exempt is honest; silently special-casing filenames would not be."""
    return bool(EXEMPT_MARKER.search(text))


def strip_code(text):
    """Blank out anything that is not the author's own running prose, preserving
    offsets so line numbers stay true.

    Blockquotes are stripped along with code. Quoting someone else's sentence,
    or an example of what not to write, is not writing it, and linting quoted
    material is how a style checker starts producing findings that cannot be
    fixed without making the document worse.
    """
    def blank(m):
        return "".join("\n" if c == "\n" else " " for c in m.group(0))
    text = OFF_ON.sub(blank, text)
    text = re.sub(r"```.*?```", blank, text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", blank, text)
    text = re.sub(r"^(?: {4}|\t).*$", blank, text, flags=re.M)
    text = re.sub(r"^\s{0,3}>.*$", blank, text, flags=re.M)     # blockquotes
    text = re.sub(r"<[^>]+>", blank, text)
    text = re.sub(r"\]\([^)]*\)", blank, text)                  # link targets
    return text


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def snippet(text, start, end, width=70):
    a = max(0, start - 25)
    b = min(len(text), end + width)
    out = text[a:b].replace("\n", " ").strip()
    return ("..." if a > 0 else "") + out + ("..." if b < len(text) else "")


def words_in(text):
    return len(re.findall(r"\b[a-zA-Z][a-zA-Z'-]*\b", text))


# --------------------------------------------------------------------- checking

def vocabulary_findings(prose, total_words):
    """Density, not presence. The guide's own rule: one or two may be
    coincidence, a pile of them in one edit is among the strongest tells."""
    hits = []
    lowered = prose.lower()
    for term, weight in AI_VOCAB.items():
        for m in re.finditer(r"\b" + re.escape(term) + r"\b", lowered):
            hits.append((term, weight, m.start()))
    for term in SENTENCE_INITIAL:
        for m in re.finditer(r"(?:^|(?<=[.!?]\s))" + term + r"\b", lowered, re.M):
            hits.append((term, 2, m.start()))

    if not hits:
        return None
    score = sum(w for _, w, _ in hits)
    per_k = (len(hits) / total_words * 1000) if total_words else 0
    # Thresholds tuned so a normal paragraph using one of these words passes.
    if len(hits) < 3 or per_k < 6:
        sev = "note"
    elif per_k < 12:
        sev = "review"
    else:
        sev = "strong"
    return {"id": "ai-vocabulary", "severity": sev,
            "count": len(hits), "score": score, "per_1000_words": round(per_k, 1),
            "terms": sorted({t for t, _, _ in hits}),
            "lines": sorted({line_of(prose, i) for _, _, i in hits}),
            "what": f"{len(hits)} words from the documented AI-overuse list "
                    f"({round(per_k, 1)} per 1000 words).",
            "fix": "These co-occur in machine text. Replace the ones that are "
                   "not carrying weight; keep any that is the right word. Do "
                   "not swap in synonyms, which is not what the tell measures."}


def rule_of_three(prose):
    """Three parallel items, especially three adjectives, repeated across a
    document. One list of three is ordinary English."""
    pat = _p(r"\b(\w+), (\w+),? and (\w+)\b")
    spots = []
    for m in pat.finditer(prose):
        a, b, c = m.groups()
        if len({a.lower(), b.lower(), c.lower()}) < 3:
            continue
        if all(len(w) > 3 for w in (a, b, c)):
            spots.append(m)
    if len(spots) < 3:
        return None
    return {"id": "rule-of-three", "severity": "review", "count": len(spots),
            "lines": [line_of(prose, m.start()) for m in spots],
            "examples": [m.group(0) for m in spots[:4]],
            "what": f"{len(spots)} three-item series.",
            "fix": "Triads are the default rhythm of generated prose. Vary the "
                   "count: two items, or four, or one specific item."}


def title_case_headings(text):
    heads = re.findall(r"^\s{0,3}#{1,6}\s+(.+)$", text, re.M)
    if len(heads) < 3:
        return None
    def is_title_case(h):
        words = [w for w in re.findall(r"[A-Za-z][\w'-]*", h) if len(w) > 3]
        if len(words) < 3:
            return False
        return sum(1 for w in words if w[0].isupper()) >= len(words) - 1
    bad = [h for h in heads if is_title_case(h)]
    if len(bad) < max(2, len(heads) * 0.6):
        return None
    return {"id": "title-case-headings", "severity": "review",
            "count": len(bad), "examples": bad[:4],
            "what": f"{len(bad)} of {len(heads)} headings are in Title Case.",
            "fix": "Use sentence case. Capitalizing every main word is one of "
                   "the more reliable structural tells."}


def boldface_density(text, total_words):
    bolds = re.findall(r"\*\*([^*\n]{1,60})\*\*", text)
    if len(bolds) < 6 or not total_words:
        return None
    per_k = len(bolds) / total_words * 1000
    lead_ins = len(re.findall(r"^\s*(?:[-*]|\d+\.)\s*\*\*[^*\n]+\*\*:", text, re.M))
    if per_k < 12 and lead_ins < 6:
        return None
    return {"id": "boldface", "severity": "review", "count": len(bolds),
            "per_1000_words": round(per_k, 1), "bold_lead_ins": lead_ins,
            "what": f"{len(bolds)} bold spans ({round(per_k,1)} per 1000 words)"
                    + (f", {lead_ins} of them bolded list lead-ins with a colon"
                       if lead_ins else "") + ".",
            "fix": "Bold the two or three things that genuinely matter. Bolding "
                   "every key term is a slide-deck habit that reads as machine "
                   "emphasis."}


def check(text):
    if is_exempt(text):
        return {"words": words_in(text), "findings": [], "human_signals": [],
                "exempt": True}
    prose = strip_code(text)
    total = words_in(prose)
    findings = []

    for cid, sev, rx, what, fix in CHECKS:
        # Character-set checks run against the raw text; code is not exempt from
        # house style when it is prose punctuation, but fenced code is.
        target = prose if cid not in ("em-dash", "curly-quote") else strip_code(text)
        seen = []
        for m in rx.finditer(target):
            seen.append(m)
        if not seen:
            continue
        findings.append({
            "id": cid, "severity": sev, "count": len(seen),
            "lines": sorted({line_of(target, m.start()) for m in seen})[:12],
            "examples": [snippet(target, m.start(), m.end()) for m in seen[:3]],
            "what": what, "fix": fix,
        })

    for extra in (vocabulary_findings(prose, total), rule_of_three(prose),
                  title_case_headings(text), boldface_density(text, total)):
        if extra:
            findings.append(extra)

    human = [name for name, rx in HUMAN_SIGNALS if rx.search(prose)]

    order = {"fix": 0, "strong": 1, "review": 2, "note": 3}
    findings.sort(key=lambda f: (order.get(f["severity"], 9), -f.get("count", 0)))
    return {"words": total, "findings": findings, "human_signals": human}


# ---------------------------------------------------------------------- output

LABEL = {"fix": "FIX", "strong": "STRONG", "review": "REVIEW", "note": "note"}


def report(name, result, quiet=False):
    lines = []
    fs = result["findings"]
    head = f"{name}  ({result['words']} words)"
    lines.append(head)
    lines.append("=" * len(head))

    if result.get("exempt"):
        lines.append("  Skipped: marked as a reference document that quotes these "
                     "tells on purpose.")
        return "\n".join(lines)
    if not fs:
        lines.append("  Nothing flagged.")
    for f in fs:
        loc = ""
        if f.get("lines"):
            shown = ", ".join(str(l) for l in f["lines"][:8])
            loc = f"  line {shown}" + ("..." if len(f["lines"]) > 8 else "")
        lines.append(f"\n  [{LABEL[f['severity']]}] {f['id']}{loc}")
        lines.append(f"    {f['what']}")
        for ex in f.get("examples", [])[:3]:
            lines.append(f"      > {ex}")
        if f.get("terms"):
            lines.append(f"      words: {', '.join(f['terms'])}")
        lines.append(f"    {f['fix']}")

    if not quiet:
        h = result["human_signals"]
        lines.append("")
        if h:
            lines.append(f"  Human-writing signals present: {', '.join(h)}.")
        else:
            lines.append("  No human-writing signals found: no plain copulas, "
                         "definite claims, or ordinary hedges.")
            lines.append("  That absence is itself worth a look. Prose with "
                         "nothing plain in it usually was not spoken first.")
    return "\n".join(lines)


def worst(result):
    sev = [f["severity"] for f in result["findings"]]
    if "fix" in sev:
        return "fix"
    if "strong" in sev:
        return "strong"
    return "review" if "review" in sev else "clean"


# ------------------------------------------------------------------- self-test

SELF_TEST_BAD = """## Course Overview And Learning Objectives

This course stands as a testament to the enduring legacy of web programming,
showcasing a vibrant, intricate, and meticulous approach to the evolving
landscape of modern development. It's not just a course, it's a journey.

Nestled in the heart of the curriculum, the project serves as a crucial
component, underscoring its importance and highlighting the transformative
power of hands-on work. Experts argue that this approach delves into the
intricacies of the field.

Despite these challenges, students continue to thrive.

In summary, this course is a pivotal moment in your education.
"""

SELF_TEST_GOOD = """## What you will build

You will build a shopping cart that survives a page reload. There are four
routes and one database table. The cart was the first thing we wrote when this
course was redesigned, because it is the smallest program that still needs every
idea in the course.

Most students finish it in about six hours. If it takes you twelve, that is
usually the database setup rather than the code, and office hours will sort it
out faster than another evening alone will.
"""


def self_test():
    bad = check(SELF_TEST_BAD)
    good = check(SELF_TEST_GOOD)
    ok = True

    bad_ids = {f["id"] for f in bad["findings"]}
    want = {"significance-puffery", "negative-parallelism", "superficial-ing",
            "challenges-formula", "summary-sentence", "vague-attribution",
            "promo-adjective", "ai-vocabulary", "copula-avoidance"}
    missing = want - bad_ids
    if missing:
        ok = False
        print(f"FAIL: sample of bad prose did not trigger {sorted(missing)}")
    else:
        print(f"ok: bad sample triggered {len(bad_ids)} checks")

    good_bad = [f for f in good["findings"] if f["severity"] in ("fix", "strong")]
    if good_bad:
        ok = False
        print(f"FAIL: clean sample flagged {[f['id'] for f in good_bad]}")
    else:
        print("ok: clean sample raised nothing above review")

    if not good["human_signals"]:
        ok = False
        print("FAIL: clean sample showed no human signals")
    else:
        print(f"ok: clean sample human signals: {', '.join(good['human_signals'])}")

    # The things the guide says are NOT tells must not fire.
    neutral = ("Furthermore, the results were robust. Moreover, the study, which "
               "was careful, perhaps overly so, used red, green, and blue markers. "
               "It is important that students, staff, and faculty agree.")
    n = check(neutral)
    fired = [f["id"] for f in n["findings"] if f["severity"] in ("fix", "strong")]
    if fired:
        ok = False
        print(f"FAIL: neutral prose with transitions/hedges/Oxford comma fired {fired}")
    else:
        print("ok: transitions, hedging, and the Oxford comma did not fire")

    print("\nSELF-TEST PASSED" if ok else "\nSELF-TEST FAILED")
    return 0 if ok else 1


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(
        description="Flag writing that reads as machine-generated.")
    ap.add_argument("files", nargs="*", help="Files to check")
    ap.add_argument("--text", help="Check this string instead of a file")
    ap.add_argument("--stdin", action="store_true", help="Read from stdin")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    ap.add_argument("--quiet", action="store_true",
                    help="Findings only, skip the human-signal summary")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    jobs = []
    if args.text:
        jobs.append(("<text>", args.text))
    if args.stdin:
        jobs.append(("<stdin>", sys.stdin.read()))
    for f in args.files:
        p = Path(f)
        if not p.exists():
            print(f"No such file: {f}", file=sys.stderr)
            return 2
        jobs.append((f, p.read_text(errors="replace")))

    if not jobs:
        ap.print_help()
        return 2

    results, rc = {}, 0
    for name, text in jobs:
        r = check(text)
        results[name] = r
        if worst(r) in ("fix", "strong"):
            rc = 1

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n\n".join(report(n, results[n], args.quiet) for n, _ in jobs))
        if rc:
            print("\nSomething above needs fixing before this text is handed over.")

    return rc


if __name__ == "__main__":
    sys.exit(main())
