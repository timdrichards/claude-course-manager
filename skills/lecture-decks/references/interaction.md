# The interactive slide

At least one slide should compute something the presenter did not decide in advance. This is the
capability that justifies building the deck in a browser at all, and it changes what happens in the
room: when a student asks "what if the load doubled," the answer is a click rather than a promise
to check.

Everything here is inline JavaScript in the one file. No framework, no build, no charting library
unless the shape genuinely needs one.

---

## The shape that works

Controls that change one parameter, a visible model that responds, and a readout of the number that
matters. Three parts, and the third is the one that gets forgotten: an animation with no number
attached is a screensaver.

```html
<section>
  <h2>What happens when the cache is cold</h2>

  <div class="controls">
    <button data-hit="0.95">95% hit rate</button>
    <button data-hit="0.50">50% hit rate</button>
    <button data-hit="0.00">cold cache</button>
  </div>

  <div class="chart" id="lat"></div>
  <p class="readout">p99 latency <span id="p99">12</span> ms</p>

  <aside class="notes">
    Run the cold case first and let the bars settle before saying anything.
    Ask what they expect at 50% before clicking it. Most guess halfway.
  </aside>
</section>
```

```html
<script>
  const bars = 40;
  const chart = document.getElementById('lat');
  const cells = Array.from({ length: bars }, () => {
    const d = document.createElement('div');
    d.className = 'bar';
    chart.appendChild(d);
    return d;
  });

  const render = (hitRate) => {
    const samples = cells.map(() => (Math.random() < hitRate ? 2 + Math.random() * 4
                                                             : 40 + Math.random() * 90));
    const max = Math.max(...samples);
    samples.forEach((ms, i) => {
      cells[i].style.height = (ms / max * 100) + '%';
      cells[i].classList.toggle('slow', ms > 30);
    });
    const sorted = [...samples].sort((a, b) => a - b);
    document.getElementById('p99').textContent =
      Math.round(sorted[Math.floor(sorted.length * 0.99)]);
  };

  document.querySelectorAll('[data-hit]').forEach((b) =>
    b.addEventListener('click', () => render(parseFloat(b.dataset.hit))));

  render(0.95);
</script>
```

```css
.chart { display: flex; align-items: flex-end; gap: 3px; height: 260px; }
.bar   { flex: 1; background: var(--accent2); transition: height .35s ease; border-radius: 2px 2px 0 0; }
.bar.slow { background: var(--accent); }
.controls button {
  font: inherit; font-size: 0.7em; padding: .5em 1em; margin-right: .5em; cursor: pointer;
  background: var(--surface); color: var(--text); border: 2px solid var(--accent2); border-radius: 8px;
}
.controls button:hover { background: var(--accent2); color: var(--bg); }
```

Forty divs with animated heights is a bar chart. It is under twenty lines, it inherits the deck's
palette for free, and it will not break when a CDN moves. A library earns its place when the chart
needs axes, scales, and tooltips, and not before.

---

## Other shapes worth stealing

- **A slider over one parameter.** `<input type="range">` with an `input` listener. Best when the
  relationship is continuous and the point is the shape of the curve.
- **A step button over an algorithm.** One click advances one iteration of the thing being taught,
  with the current state highlighted. This is the strongest form for anything with a loop invariant.
- **A text box that parses as you type.** For grammars, regular expressions, selectors, or query
  syntax. Show the parse, not only the verdict.
- **A grid that fills.** Hashing, paging, memory layout, scheduling. Cells with a color and a label
  cover a surprising amount of a systems curriculum.
- **A stopwatch race.** Two implementations, real timers, real numbers. Say out loud that a
  microbenchmark in a browser is not a benchmark; the honesty is itself worth teaching.

---

## Keeping it under control during a live lecture

**Reset when the slide is entered.** A demo left in whatever state it reached last time is how a
second run of the same lecture goes strange. Reveal fires events on its own object:

```html
<script>
  Reveal.on('slidechanged', (event) => {
    if (event.currentSlide.querySelector('#lat')) render(0.95);
  });
</script>
```

`Reveal.on('ready', ...)` is the hook for anything that must run once the deck has laid out.

**Stop anything that runs on a timer when the slide is left.** An interval left running behind
thirty slides will still be running at the end of the class, and on a battery-powered laptop that
is felt.

```html
<script>
  let timer = null;
  Reveal.on('slidechanged', (event) => {
    clearInterval(timer);
    if (event.currentSlide.dataset.live === 'ticker') {
      timer = setInterval(tick, 250);
    }
  });
</script>
```

**Make it deterministic enough to rehearse.** Pure `Math.random()` means the demo an instructor
practiced is not the demo the class sees. When the shape of the result carries the argument, seed a
small generator so every run tells the same story:

```js
let seed = 42;
const rand = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
```

**Never use `localStorage` or `sessionStorage`.** Keep state in variables. Browser storage is
unavailable in some contexts the deck will be viewed in and buys nothing for a fifty minute class.

**Keep the click targets large.** These get pressed by someone standing at a podium, sometimes on a
clicker-driven mirror of the screen, often without looking. Buttons below about 0.7em of the deck's
base size are hard to hit.

---

## The signature element

A small always-visible motif is different from an interactive slide, and the two work well
together. A live readout in a corner, a progress rail keyed to the deck's sections, a token stream
in the footer: something that ticks quietly and reinforces the subject without demanding attention.

Keep it to one, keep it out of the content area, and make sure it survives the auto-animate slides,
which means putting it outside `.slides` or fixing its position so reveal does not try to pair it
across sections.

```html
<div class="hud" aria-hidden="true">
  <span id="hud-rps">0</span> req/s
  <span class="sep">.</span>
  p99 <span id="hud-p99">0</span> ms
</div>
```

`aria-hidden` because it is decoration; a screen reader should not narrate a number that means
nothing out of context.
