# The scaffold

Everything in this file has been verified against reveal.js 5.1.0 in a real browser. The numbers
are measured rather than estimated.

---

## The files to load

These returned 200 from cdnjs at the time of writing. Check them again before relying on them,
because cdnjs prunes versions.

```bash
for u in \
  https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.css \
  https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.js \
  https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/highlight/highlight.min.js \
  https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/notes/notes.min.js \
  https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/base16/eighties.min.css \
; do printf "%-95s " "$u"; curl -s -o /dev/null -w "%{http_code}\n" -I "$u"; done
```

Other plugins on the same path, all present in 5.1.0: `plugin/math/math.min.js`,
`plugin/zoom/zoom.min.js`, `plugin/search/search.min.js`, `plugin/markdown/markdown.min.js`. Load
only what the deck uses. Version 5.2.1 also resolves if a newer pin is wanted; do not mix versions
across files.

Do not load a reveal theme file. A theme is the thing being replaced by the custom design, and
loading one only produces specificity fights.

The highlight.js style is a separate concern from the reveal theme and does need loading. Pick one
whose background suits the deck: `base16/eighties` is a mid-dark grey that sits well on most dark
themes.

---

## What reveal 4 boilerplate gets wrong

Most reveal examples on the web are version 3 or 4 and fail silently against 5.x. If any of these
appear in a draft, they came from a stale example:

- `print/pdf.css` or `print/pdf.min.css`. This 404s on 5.x; print styles are compiled into
  `reveal.min.css` and load through an `@media print` block with nothing to link.
- `css/reveal.css`, `js/reveal.js`, `lib/js/head.min.js`. All version 3 paths.
- `Reveal.initialize({ dependencies: [...] })`. Replaced by `plugins: [...]` with named globals.

---

## The head

The theme block is the part to design. Everything outside it is mechanical and should be copied
close to verbatim.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>COMPSCI 426 . Lecture 7 . Caching</title>

<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/base16/eighties.min.css">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap">

<style>
  /* ---- the design, replaced per deck ---- */
  :root {
    --bg:      #0b1a2b;
    --surface: #12293f;
    --text:    #e6eef7;
    --muted:   #8fa8c0;
    --accent:  #ffb703;
    --accent2: #2ec4b6;
    --display: 'Inter', system-ui, sans-serif;
    --mono:    'JetBrains Mono', ui-monospace, monospace;
  }

  /* ---- REQUIRED. reveal.min.css hardcodes this wrapper to white. ---- */
  .reveal-viewport {
    background-color: var(--bg) !important;
    color: var(--text) !important;
  }

  .reveal { font-family: var(--display); color: var(--text); font-size: 32px; }
  .reveal h1, .reveal h2, .reveal h3 { font-family: var(--display); color: var(--accent);
    text-transform: none; letter-spacing: -0.01em; }
  .reveal h1 { font-size: 2.1em; }
  .reveal h2 { font-size: 1.5em; }
  .reveal p, .reveal li { font-size: 1em; line-height: 1.35; }
  .reveal pre { width: 100%; box-shadow: none; font-size: 0.62em; }
  .reveal pre code { font-family: var(--mono); padding: 0.8em 1em; border-radius: 8px;
    max-height: none; line-height: 1.35; }
  .reveal code { font-family: var(--mono); }
  .reveal section { text-align: left; }
  .reveal .eyebrow { font-size: 0.55em; letter-spacing: 0.18em; text-transform: uppercase;
    color: var(--accent2); }
</style>
</head>
```

`text-align: left` is worth setting deliberately. Reveal centers everything by default, which
looks fine on a title slide and makes a body slide harder to scan.

---

## The init block

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/reveal.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/highlight/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/5.1.0/plugin/notes/notes.min.js"></script>
<script>
  Reveal.initialize({
    width: 1050,
    height: 660,
    margin: 0.06,
    minScale: 0.2,
    maxScale: 2.0,
    hash: true,
    slideNumber: 'c/t',
    transition: 'slide',
    transitionSpeed: 'fast',
    autoAnimateDuration: 0.8,
    autoAnimateEasing: 'ease-out',
    plugins: [RevealHighlight, RevealNotes]
  });
</script>
```

`hash: true` puts the slide in the URL, which is what lets an instructor reload mid-lecture and
land back where they were. `slideNumber: 'c/t'` shows position out of total, which students ask
about constantly.

---

## Sizing for a lecture hall

Reveal renders the deck at the configured `width` by `height` and then scales that whole canvas to
fit the window:

```
scale = min(screen_w / deck_w, screen_h / deck_h) x (1 - 2 x margin)
```

On any 16:9 screen with a deck less wide than 16:9, the height term is smaller, so **height is the
only lever that matters**. Widening the deck from 960 to 1050 changes the scale factor by nothing
at all. This is measured, not inferred:

| Screen | Deck 960x700 | Deck 1050x700 | Deck 980x620 | Deck 1280x720 |
|---|---|---|---|---|
| 1920x1080 | 1.45 | 1.45 | 1.64 | 1.41 |
| 1440x900 | 1.21 | 1.21 | 1.36 | 1.06 |
| 1280x800 | 1.07 | 1.07 | 1.21 | 0.94 |

Reveal's own defaults are 960x700, `margin: 0.04`, `minScale: 0.2`, `maxScale: 2.0`. A deck height
between 620 and 680 gives a useful lift over the default without squeezing the slide so hard that
content stops fitting. Height below about 600 starts costing more in vertical room than it returns
in scale.

Scale alone is not enough, because a 20px source font on a 960x700 deck still lands at 29px on a
1080p projector, which is small at the back of a hall. Set the base explicitly and hold these
floors:

| Element | Source size | Rendered at 1920x1080, deck 1050x660 |
|---|---|---|
| `.reveal` base | 32px | 46px |
| Body text and list items | 1em (32px) | 46px |
| Code blocks | 0.62em (20px) | 29px |
| Eyebrow and captions | 0.55em (18px) | 26px |
| Diagram node labels | 0.7em (22px) | 32px |

Code is the thing that goes wrong. It is monospaced, it is dense, and it is the content students
most need to read precisely. Twenty source pixels is a floor rather than a target, and a code block
that needs to be smaller than that to fit is a block that needs fewer lines. Ten to twelve lines is
about the limit for a slide.

Verify by loading the deck and shrinking the browser window to roughly the projector's aspect
ratio, then standing back from the screen. If the code is uncomfortable at arm's length on a
laptop, it is unreadable from row twenty.

---

## PDF export

Reveal 5 compiles its print styles into `reveal.min.css`, so there is nothing extra to link. Open
the deck with `?print-pdf` appended before the hash and print to PDF from the browser, with
backgrounds enabled and margins set to none:

```
file:///path/to/deck.html?print-pdf
```

Say plainly what this loses. Auto-animate pairs export as two separate static slides, which is
usually the right handout anyway since it shows before and after. Interactive slides export as
whatever state they happened to be in. A deck whose whole argument is one live simulation does not
become a good PDF, and it is more honest to say so than to ship a handout with a dead widget on
page six.

---

## Self-contained means self-contained

One file. Inline every rule of CSS and every line of JavaScript. Images go in as `data:` URLs, or
better, get drawn with CSS and inline SVG so the file stays small enough to email.

The only external references are the CDN scripts and the web font, and both degrade acceptably:
without a network the fonts fall back to the system stack, though reveal itself will not load, so
a deck that must survive a dead podium network needs its reveal files vendored alongside it. That
is a deliberate trade rather than an accident, and worth mentioning to an instructor presenting
somewhere with unreliable wifi.

---

## Looking at it rendered

The checks in `deck_check.py` are static. They cannot see that a code block is clipped, that a
diagram runs off the slide, or that a caption sits under the footer. Those are the errors an
audience notices first, and they are cheap to find:

```javascript
// node screenshot.js, with playwright available
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file:///abs/path/deck.html');
  await p.waitForTimeout(2000);
  const n = await p.evaluate(() => Reveal.getTotalSlides());
  for (let i = 0; i < n; i++) {
    await p.evaluate(j => Reveal.slide(j), i);
    await p.waitForTimeout(600);
    const over = await p.evaluate(() => {
      const s = document.querySelector('.slides section.present');
      return s ? s.scrollHeight > s.clientHeight + 4 : false;
    });
    await p.screenshot({ path: `shot-${String(i).padStart(2, '0')}.png` });
    if (over) console.log('overflows:', i);
  }
  console.log('page errors:', errs);
  await b.close();
})();
```

Then open the screenshots and look at them. Reading the numbers is not the same as seeing the
slide, and the whole point of the deck is that someone sees it.

If no browser is available, say plainly when handing the deck over that the visual pass was not
done. An instructor who knows that will click through it once before class. An instructor told the
deck was verified will not.
