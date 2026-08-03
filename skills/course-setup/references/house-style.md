# House style

Rules for anything this plugin writes that a student, a colleague, or the instructor will read.
They are shared deliberately: a syllabus, an announcement, an assignment spec, and a line of
grading feedback should sound like the same person wrote them, because the same person did.

A course profile's `Voice` section overrides anything here. These are the defaults when it is
silent, and they are drawn from what the instructor's own course files already enforce.

---

## The check that runs before anything is handed over

Everything drafted here goes out under the instructor's name. If it reads as machine output,
students discount it, and an instructor who requires students to disclose their AI use has failed
their own standard.

So this is a required step, not advice. Before handing over any drafted prose:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py draft.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py --text "the paragraph"
```

Everything it labels `FIX` gets fixed. Everything labelled `STRONG` gets fixed unless there is a
reason to keep it, and the reason gets said out loud. `REVIEW` findings are judgment.

`ai-tells.md` in this same folder is the full account: what each tell is, why it shows up, what
human writing looks like instead, and, just as important, the list of famous "AI tells" that are
nothing of the sort. Read it before rewriting anything to sound more human, because removing
hedges and transitions makes prose worse and no less synthetic.

The rules below are the parts of that reference that are absolute here.

---

## No em-dashes

Never use an em-dash (`—`). Not in Canvas prose, not in emails, not in check-in messages to
students, not in grading feedback, not in commit messages, not in a skill's own documentation.

Use a comma, a period, or a semicolon, whichever actually fits the sentence, rather than reaching
for `—` as a default connector. Most sentences that want an em-dash want a period.

En-dashes in number ranges are fine and correct: `Units 8–11`, `pages 40–52`.

Proofread before publishing and fix any that slipped in. This is the single most-repeated style
rule in the instructor's course files, and it is enforced on slide decks by sweeping visible text
before shipping. Pre-existing violations in already-published material are out of scope unless
someone asks for a sweep; do not silently rewrite live pages to fix them.

---

## Tone

Direct and professional, with no fluff. Favor students making informed decisions over prescriptive
rules where a choice is genuinely theirs. Be explicit about consequences rather than issuing vague
warnings.

Avoid passive voice in policy language. "We deduct points" rather than "submissions are
penalized." Naming the actor makes the policy checkable and makes the course accountable for it.

Honesty over tidiness. If a claim was true and is no longer, rewrite it to be accurate rather than
preserving a neat sentence. A real instance worth remembering: a unit's prose claimed two files
"do not change at all," which became false once two bugs were found, and the fix was to name both
one-line changes honestly rather than keep the tidier false economy.

---

## Signatures

- **Announcements** carry no signature or sign-off line at all.
- **Emails and LMS messages** sign `~ Prof. Richards`, or the instructor's own equivalent from the
  course profile.
- **Grading feedback** carries no signature.

These differ on purpose. An announcement is the course speaking; an email is a person speaking.

---

## Title emoji prefixes

Canvas titles carry a leading emoji so the module list is scannable. Pick the matching one; do not
invent a new one without a reason.

**Pages:** `⚖️` syllabus, `⭐︎` welcome, `⛯` setup and onboarding, `⌯ⲗ` knowledge units,
`ᯓ` project, `🧩` supplementary technical reference.

**Module items:** `🔬` Lab, `🛠️` Homework, `🧱` Sprint, `✔️` Quiz, `🪞` Reflection,
`💬` Discussion, `🎬` video, `📊` slides.

A course that does not use this convention should not have it imposed; check what the course's
existing titles already do before adding a prefix.

---

## Formatting

Use plain bullet lists for policy enumerations. Tables are right for grading breakdowns and
schedule overviews, and wrong for prose that happens to have two parts.

Keep heading hierarchy shallow. Two levels is almost always enough, and a syllabus that needs
four is usually one that should be split.

Do not number sections unless the course already numbers them. Numbered sections are a
maintenance burden: inserting one renumbers everything downstream, and every cross-reference
elsewhere goes stale silently.

---

## Writing about tools and code

Course JS style, where a course does not say otherwise: arrow functions, ES6 modules, no classes,
no traditional `for` loops. This is a teaching constraint rather than a universal preference, and
it exists so students meet the underlying idea before the shorthand.

Show the literal command for any imperative instruction. "Install the Tailwind CLI" is not
actionable; `npm install -D tailwindcss @tailwindcss/cli` is. When a fix applies to "the
controller" or "the handler" and more than one could be meant, name the specific function.

Paraphrase external documentation rather than quoting it. Reproducing vendor documentation at
length is a copyright problem, and a paraphrase aimed at this course's students is usually more
useful anyway.

---

## Two rules that are not style, and matter more

**Never invent a fact about the course.** A date, a room, a policy, a staff member's
availability, a point value. Leave a marked gap instead: `[CHECK: is the exam room confirmed?]`.
Course staff fill that in seconds and cannot un-send a wrong room number to 200 people.

**Never launder a private disclosure.** When generalizing across student writing, exclude
anything a student plausibly meant only for the instructor: health, family, financial,
immigration, disability or accommodation context. Do not soften it into "someone mentioned
struggling with X" and keep it. Leave that student out of the pattern entirely.
