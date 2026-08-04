# Auto-animate

The one reveal feature worth building a deck around. Two consecutive `<section data-auto-animate>`
elements, with matching `data-id` attributes on corresponding children, tween between states rather
than cutting.

No plugin is needed. Auto-animate is core reveal, not an add-on.

What reveal does at runtime, observed in the DOM: every element it manages to pair across the two
slides gets a `data-auto-animate-target` index and is animated from its old geometry and computed
style to its new ones. Every element it cannot pair gets `data-auto-animate-target="unmatched"` and
is faded rather than moved. Knowing this is what makes the failure modes below diagnosable, because
you can open devtools mid-transition and read which is which.

Global tuning lives in `Reveal.initialize`: `autoAnimateDuration` (seconds, default 1.0),
`autoAnimateEasing` (default `ease`), and `autoAnimateUnmatched` (default true, fades the
unmatched). Per-element overrides go on the element as `data-auto-animate-duration`,
`data-auto-animate-easing`, `data-auto-animate-delay`, and `data-auto-animate-unmatched`.

Around 0.8s reads well in a lecture hall. Faster and the eye misses the movement it was supposed to
follow; slower and the room starts waiting.

---

## Recipe 1: the code diff

The highest-value use, and the reason to prefer this over a screenshot of a diff. Give both `<pre>`
elements the same `data-id`. Reveal diffs the two code blocks line by line: shared lines glide to
their new positions, added lines fade in, removed lines fade out.

```html
<section data-auto-animate>
  <h2 data-id="hdr">Adding a cache</h2>
  <pre data-id="code"><code class="language-js" data-trim data-line-numbers>
const fetchUser = (id) => {
  return db.get(id);
};
  </code></pre>
</section>

<section data-auto-animate>
  <h2 data-id="hdr">Adding a cache</h2>
  <pre data-id="code"><code class="language-js" data-trim data-line-numbers="2-3">
const fetchUser = async (id) => {
  const hit = await cache.get(id);
  if (hit) return hit;
  return db.get(id);
};
  </code></pre>
</section>
```

The `data-id` goes on the `<pre>`, not on the `<code>`. Reveal looks for the wrapper.

`data-trim` strips the leading whitespace that indenting the HTML introduces, so the code renders
flush. Without it every line carries the markup's indentation.

`data-line-numbers="2-3"` highlights the changed lines on the second slide and dims the rest, which
is worth adding whenever the change is more than one line. The syntax also takes steps separated by
`|` (`data-line-numbers="1|2-3|5"`) to walk the class through a block one region at a time, which
is a different tool from auto-animate and composes with it.

Keep the pair to one conceptual edit. Three slides showing three successive edits teach better than
one slide where six lines change at once, and they cost nothing extra to present.

---

## Recipe 2: the diagram that grows a box

Give each node a stable `data-id`. When a node is inserted between two others, the others slide
apart to make room instead of the whole picture jumping.

```html
<section data-auto-animate>
  <div class="row">
    <div class="node" data-id="cli">Client</div>
    <div class="node" data-id="api">API</div>
    <div class="node" data-id="db">DB</div>
  </div>
</section>

<section data-auto-animate>
  <div class="row">
    <div class="node" data-id="cli">Client</div>
    <div class="node" data-id="api">API</div>
    <div class="node accent" data-id="cache">Cache</div>
    <div class="node" data-id="db">DB</div>
  </div>
</section>
```

Verified behavior: `cli`, `api`, and `db` are paired and animate to their new positions, while
`cache` is tagged unmatched and fades in over them. The effect is that the new component visibly
arrives into an existing system, which is the pedagogical point.

Ordinary flexbox does the layout. Nothing here needs a diagramming library, and hand-written divs
survive a design change that a generated SVG will not.

Removing a node works the same way in reverse, and is underused. Showing a system, then showing it
with a component taken away, is how to teach what that component was doing.

---

## Recipe 3: the number that climbs

Any element holding a number or short string will tween its position and its computed style,
including font size and color.

```html
<section data-auto-animate>
  <p class="eyebrow">Requests per second</p>
  <div class="stat" data-id="rps" style="font-size: 2em">1,200</div>
</section>

<section data-auto-animate>
  <p class="eyebrow">Requests per second</p>
  <div class="stat" data-id="rps" style="font-size: 5em; color: var(--accent)">48,000</div>
</section>
```

Reveal interpolates the font size rather than the digits, so the number swaps while the type grows.
That reads as emphasis, which is usually what is wanted. Counting the digits up requires the
interactive approach instead.

---

## Failure modes

**The second section is missing `data-auto-animate`.** Nothing animates and nothing warns. The
slide just cuts, and because a cut is a perfectly normal slide change it is easy to stare at this
for a while. Confirmed behavior: the element ends at its new size with no `data-auto-animate-target`
attribute and no tween. If a morph is not morphing, check this first.

**A `data-id` appears twice in the same section.** Reveal still pairs them, in document order,
which means it usually works and occasionally pairs the wrong two elements after an edit reorders
something. Keep ids unique within a section.

**Nothing shares a `data-id` across the pair.** Every element is unmatched, so the whole slide
cross-fades. This looks deliberate enough to ship by accident.

**The morph should restart.** When two identical states need to animate again, put
`data-auto-animate-restart` on the later section.

**Different elements share an id by coincidence.** `data-id="title"` on a heading in one pair and a
caption in another is fine, since matching only happens between consecutive slides. Reuse across
distant slides costs nothing.

---

## When not to use it

A deck where every transition morphs is as monotonous as one where none do, and the effect stops
carrying meaning once it is the default. Auto-animate should mean "watch this specific thing
change." Use ordinary slides for everything else, and let the contrast do the work.

Fragments (`class="fragment"`) are the right tool for revealing bullet points one at a time, which
is a different job: fragments add material to a static slide, auto-animate transforms material
across two slides. Reaching for auto-animate to reveal a list is more markup for a worse result.
