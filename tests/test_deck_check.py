"""Tests for deck_check.py.

The checks worth testing are the silent ones. A deck with a missing viewport
override, an unpaired auto-animate section, or a reveal 4 path renders without
raising anything in a browser, which is exactly why the checker exists and why
a regression in it would go unnoticed.
"""

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dc = load("deck_check")


def ids(html):
    return {f["id"] for f in dc.check_deck(html)["findings"]}


def sev(html, cid):
    for f in dc.check_deck(html)["findings"]:
        if f["id"] == cid:
            return f["severity"]
    return None


HEAD = """<html><head><title>T</title><style>
:root { --bg:#0b1a2b; --text:#e6eef7; }
%s
.reveal { font-size: 32px; }
</style></head><body><div class="reveal"><div class="slides">"""

FOOT = """</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/notes/notes.min.js"></script>
<script>
Reveal.initialize({ width: 1050, height: 660, plugins: [RevealNotes] });
document.body.addEventListener('click', () => {});
</script></body></html>"""

OVERRIDE = (".reveal-viewport { background-color: var(--bg) !important; "
            "color: var(--text) !important; }")


def deck(body, override=OVERRIDE):
    return (HEAD % override) + body + FOOT


class TestSelfTest(unittest.TestCase):
    def test_bundled_self_test_passes(self):
        self.assertEqual(dc.self_test(), 0)


class TestViewportOverride(unittest.TestCase):
    """reveal.min.css sets .reveal-viewport to white. Missing this override is
    the most common way a dark deck ships looking broken."""

    def test_missing_is_a_failure(self):
        self.assertEqual(sev(deck("<section>x</section>", override=""),
                              "viewport-override"), "fail")

    def test_present_is_clean(self):
        self.assertNotIn("viewport-override", ids(deck("<section>x</section>")))

    def test_comment_does_not_count(self):
        html = deck("<section>x</section>", override="/* .reveal-viewport goes here */")
        self.assertEqual(sev(html, "viewport-override"), "fail")

    def test_rule_without_background_is_a_failure(self):
        html = deck("<section>x</section>", override=".reveal-viewport { color: #fff; }")
        self.assertEqual(sev(html, "viewport-override"), "fail")

    def test_missing_important_is_only_a_warning(self):
        html = deck("<section>x</section>",
                    override=".reveal-viewport { background-color: #0b1a2b; }")
        self.assertEqual(sev(html, "viewport-important"), "warn")


class TestAutoAnimatePairing(unittest.TestCase):
    PAIR = ('<section data-auto-animate><pre data-id="c">a</pre></section>'
            '<section data-auto-animate><pre data-id="c">b</pre></section>')

    def test_a_correct_pair_is_clean(self):
        found = ids(deck(self.PAIR))
        self.assertNotIn("auto-animate-orphan", found)
        self.assertNotIn("auto-animate-no-match", found)

    def test_lone_section_is_caught(self):
        html = deck('<section data-auto-animate><pre data-id="c">a</pre></section>'
                    '<section><pre data-id="c">b</pre></section>')
        self.assertEqual(sev(html, "auto-animate-orphan"), "fail")

    def test_pair_sharing_no_id_is_caught(self):
        html = deck('<section data-auto-animate><pre data-id="a">a</pre></section>'
                    '<section data-auto-animate><pre data-id="b">b</pre></section>')
        self.assertEqual(sev(html, "auto-animate-no-match"), "fail")

    def test_duplicate_id_within_a_section_warns(self):
        html = deck('<section data-auto-animate><p data-id="d">a</p><p data-id="d">b</p></section>'
                    '<section data-auto-animate><p data-id="d">c</p></section>')
        self.assertEqual(sev(html, "auto-animate-dup-id"), "warn")

    def test_vertical_stacks_pair_within_their_parent(self):
        """Nested sections are a vertical stack. A pair inside one is a real
        pair, and must not be compared against its parent's siblings."""
        html = deck('<section><section data-auto-animate><p data-id="v">1</p></section>'
                    '<section data-auto-animate><p data-id="v">2</p></section></section>')
        found = ids(html)
        self.assertNotIn("auto-animate-orphan", found)
        self.assertNotIn("auto-animate-no-match", found)


class TestLegacyReveal(unittest.TestCase):
    def test_reveal4_print_stylesheet(self):
        html = deck("<section>x</section>").replace(
            "</style>", "</style><link href='https://x/reveal.js/5.1.0/print/pdf.min.css'>")
        self.assertEqual(sev(html, "legacy-reveal-path"), "fail")

    def test_dependencies_option(self):
        html = deck("<section>x</section>").replace("plugins: [RevealNotes]",
                                                    "dependencies: []")
        self.assertEqual(sev(html, "legacy-dependencies"), "fail")

    def test_mixed_versions(self):
        html = deck("<section>x</section>").replace("5.1.0/plugin", "5.2.1/plugin")
        self.assertEqual(sev(html, "version-mix"), "fail")


class TestSelfContained(unittest.TestCase):
    def test_local_stylesheet_is_a_failure(self):
        html = deck("<section>x</section>").replace(
            "</style>", "</style><link rel='stylesheet' href='./theme.css'>")
        self.assertEqual(sev(html, "not-self-contained"), "fail")

    def test_data_urls_are_fine(self):
        html = deck("<section><img src='data:image/png;base64,iVBOR'></section>")
        self.assertNotIn("not-self-contained", ids(html))

    def test_preconnect_hint_is_not_a_fetchable_url(self):
        """A preconnect names an origin to warm up. HEADing it 404s, and a
        checker that reports that gets the useful hint deleted."""
        html = deck("<section>x</section>").replace(
            "</style>", "</style><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>")
        parser = dc.DeckParser()
        parser.feed(html)
        hinted = [u for _, u, hint in parser.links if hint]
        self.assertEqual(hinted, ["https://fonts.gstatic.com"])
        self.assertNotIn("not-self-contained", ids(html))

    def test_anchors_are_fine(self):
        self.assertNotIn("not-self-contained", ids(deck("<section><a href='#2'>x</a></section>")))

    def test_browser_storage_is_a_failure(self):
        html = deck("<section>x</section>").replace(
            "Reveal.initialize", "localStorage.setItem('a',1); Reveal.initialize")
        self.assertEqual(sev(html, "browser-storage"), "fail")


class TestHouseStyle(unittest.TestCase):
    def test_em_dash_in_slide_text(self):
        self.assertEqual(sev(deck("<section><p>a — b</p></section>"), "em-dash"), "fail")

    def test_em_dash_inside_code_is_ignored(self):
        """Code is quoted material. Linting it produces findings that cannot be
        fixed without changing what the slide teaches."""
        html = deck("<section><pre><code>const s = 'a — b';</code></pre></section>")
        self.assertNotIn("em-dash", ids(html))

    def test_em_dash_in_a_script_is_ignored(self):
        html = deck("<section>x</section>").replace(
            "Reveal.initialize", "// a — comment\nReveal.initialize")
        self.assertNotIn("em-dash", ids(html))

    def test_curly_quotes(self):
        self.assertEqual(sev(deck("<section><p>“x”</p></section>"), "curly-quote"), "fail")

    def test_todo_marker_is_case_sensitive(self):
        self.assertEqual(sev(deck("<section><p>TODO check</p></section>"), "todo-marker"), "fail")
        self.assertNotIn("todo-marker", ids(deck("<section><p>a todo list</p></section>")))


class TestSizing(unittest.TestCase):
    def test_small_base_font_warns(self):
        html = deck("<section>x</section>").replace("font-size: 32px", "font-size: 20px")
        self.assertEqual(sev(html, "base-font-small"), "warn")

    def test_tall_deck_warns(self):
        html = deck("<section>x</section>").replace("height: 660", "height: 900")
        self.assertEqual(sev(html, "deck-too-tall"), "warn")

    def test_default_size_warns(self):
        html = deck("<section>x</section>").replace("width: 1050, height: 660, ", "")
        self.assertEqual(sev(html, "deck-size-default"), "warn")

    def test_sizing_problems_never_fail_the_run(self):
        """Legibility is a judgment call about a specific room. It should be
        reported, and it should not block handing a deck over."""
        html = deck("<section>x</section>").replace("font-size: 32px", "font-size: 20px")
        self.assertFalse([f for f in dc.check_deck(html)["findings"]
                          if f["severity"] == "fail"])


class TestPlugins(unittest.TestCase):
    def test_notes_without_the_plugin(self):
        html = deck('<section>x<aside class="notes">n</aside></section>').replace(
            "plugins: [RevealNotes]", "plugins: []")
        self.assertEqual(sev(html, "notes-plugin-missing"), "fail")

    def test_highlighted_code_without_the_plugin(self):
        html = deck('<section><pre><code class="language-js">x</code></pre></section>')
        self.assertEqual(sev(html, "highlight-plugin-missing"), "fail")

    def test_no_notes_anywhere_warns(self):
        self.assertEqual(sev(deck("<section>x</section>"), "no-speaker-notes"), "warn")

    def test_uncleared_interval_warns(self):
        html = deck("<section>x</section>").replace(
            "Reveal.initialize", "setInterval(tick, 250); Reveal.initialize")
        self.assertEqual(sev(html, "timer-never-cleared"), "warn")


class TestNotADeck(unittest.TestCase):
    def test_plain_html_is_reported_once(self):
        r = dc.check_deck("<html><body><p>hello</p></body></html>")
        self.assertEqual([f["id"] for f in r["findings"]], ["not-a-deck"])


class TestStats(unittest.TestCase):
    def test_counts(self):
        s = dc.check_deck(deck(TestAutoAnimatePairing.PAIR +
                               '<section>x<aside class="notes">n</aside></section>'))["stats"]
        self.assertEqual(s["sections"], 3)
        self.assertEqual(s["auto_animate_sections"], 2)
        self.assertEqual(s["speaker_notes"], 1)
        self.assertEqual(s["deck_size"], "1050x660")
        self.assertEqual(s["reveal_versions"], ["5.1.0"])


if __name__ == "__main__":
    unittest.main()
