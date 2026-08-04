# Course Manager

Nine skills that share one idea: **a course is a folder**, and everything about it lives in that
folder in a shape every skill understands. Set a course up once and the syllabus skill, the grading
skill, the lecture deck builder, and the Piazza digest all know the same facts about it.

You drive all of it by asking. There are scripts underneath, and you never have to run one.

## Installing

This repository is a Claude plugin and doubles as a single-plugin marketplace, so it installs from
the repo itself:

```
/plugin marketplace add timdrichards/claude-course-manager
/plugin install course-manager@claude-course-manager
```

Or clone it and point Claude at the folder. The plugin needs Python 3.9 or newer. Two skills want
extra packages, and Claude will tell you when you first need them:

```bash
pip install piazza-api                # student-questions
pip install requests beautifulsoup4   # gradescope
```

Nothing is configured globally. Everything is per course, in a folder you choose.

## Start here

Say this:

> Set up COMPSCI 326 for the fall.

Claude asks what it needs and does the rest: where your courses should live, the course number and
title, the term, your institution, and which platforms you use. It creates the folder, writes the
config, and tells you exactly which credential files to fill in and where to get each token. If
you are not sure whether a course already exists, ask "what courses do I have set up" first.

Then build the course profile, which is the file every other skill reads:

> Build a course profile for 326 from my syllabus and last term's schedule.

The profile carries what the course teaches, its policies, its staff, and its voice. It is worth
twenty minutes once, because it is what stops every later answer from being generic. When something
changes mid-term, say "update the 326 profile, the late policy is now three days" and it is
recorded for everything downstream.

If a platform is missing, ask for it directly:

> Connect Canvas to 326. The course id is 123456 and we're on umass.instructure.com.

> My Piazza credentials aren't working for 326.

Claude also suggests connectors when a request needs one it does not have. If you ask it to put a
deck in your Drive or check something on your calendar, it will tell you what to connect rather
than quietly failing.

## Things to ask for

### Setting up and keeping straight

> What courses do I have, and is anything misconfigured?

> Check my 326 setup before the semester starts.

> Roll 326 over to spring. New term, same course.

> Where do my courses live?

### The syllabus

> Draft a syllabus for 326. Three credits, fifteen weeks, about 200 students, no exams, one project.

> Review my syllabus for consistency.

> Does the syllabus match what I'm actually doing in Canvas?

That last one is the one worth running. It fetches the live course and compares: assignment counts,
gradebook weights, the configured late policy against the text, quiz lengths. A syllabus that
promises a two-day late cutoff while Canvas is configured with none is how a grade dispute starts.

> The late policy changed. Update the syllabus and tell the class.

> Make a syllabus quiz, ten questions, over the parts students get wrong.

### Lecture decks

> Build me a deck on hash tables for Thursday. 50 minutes, and I want to morph the code from
> linear probing to chaining so they can see the difference.

> Turn these notes into slides for Tuesday. [paste notes]

> Make a slide where I can crank the load factor up and down live and they watch collisions climb.

Decks come out as one self-contained HTML file, built on reveal.js, that you open on the podium
machine. Animated code diffs, diagrams that grow a component, an interactive slide you can drive
during a lecture, and speaker notes only you see. Ask for a PDF handout and Claude will make one
and tell you honestly what the interactive slides lose in the conversion.

### Assignments

> Write the spec for homework 3. It's the routing assignment, about six hours of work.

> Is this spec clear? Students keep asking the same question about part 2.

> Scope this project honestly. I think it's too big for two weeks.

> Turn that spec into a Canvas assignment, due the 14th.

### Student questions

> A student posted this on Piazza, how should I answer it? [paste]

> Check Piazza for anything unanswered.

> Did anyone leak assignment code in a public post?

Replies come back Socratic by default: they move the student forward without handing over the
answer. Nothing posts until you say so. You can also ask for a digest every morning, which is the
next section.

### Grading

> Write a rubric for the project milestone.

> Help me grade these. [drop in submissions or a Gradescope export]

> Draft feedback for this submission against the rubric.

> Are my TAs grading consistently?

> This student is asking for a regrade on problem 4. Here's what they wrote.

> Push these scores to Canvas.

Claude asks how involved you want it to be before it starts, because "help me grade" means very
different things to different people.

### Talking to the class

> Announce that the deadline moved to Monday.

> Email the class about the exam room change.

> Write to my TAs about the grading meeting.

> There's an error in problem 3. Post a correction.

Announcements go out unsigned, emails sign off as you. Nothing is sent without you seeing it first.

### Knowing how the class is doing

> Who's falling behind?

> Who hasn't submitted homework 4?

> Compute final grades and audit them before I submit.

> How is the class doing overall?

### Canvas, directly

> Pull the roster for 326.

> What's ungraded?

> Give this student an extension to Friday.

> Set up project teams from this CSV.

> Import the Gradescope scores into the midterm assignment.

## Things to schedule

Ask for a recurring task and Claude sets it up:

> Every weekday at 8am, check Piazza for unanswered questions and draft replies for me to review.

> Every Monday, tell me who's fallen behind in 326.

Scheduled runs draft and stop. Nothing posts, announces, or grades while you are not watching,
because the approval cannot have happened. You come back to drafts waiting for a yes.

## What it will not do without you

**Two switches on every write.** Writing to Canvas, and privatizing a Piazza post, both need the
command flag and the course's config set to `"live"`. Either one missing and it prints what it
would do and stops. The flag is easy to trigger by accident; the config file is a decision you
made once, after watching the thing do the right thing on real data.

Every write records the previous value, so you can always ask "what did you change, and how do I
undo it."

**Never invents a fact about your course.** A date, a room, a policy, a point value. It leaves a
marked gap instead, like `[CHECK: is the exam room confirmed?]`, and lists them when it hands the
draft over. You can fill those in seconds; you cannot un-send a wrong room number to 200 people.

**Never publishes anything student-visible without showing you the exact change first.**

## Writing that reads as yours

Everything this plugin drafts goes out under your name. A syllabus, an announcement, a line of
feedback on a student's work. If it reads as machine output, students discount it, and an
instructor who asks students to disclose their AI use has just failed their own standard.

So every skill that drafts prose runs a check before handing anything over. The tells come from
Wikipedia's *Signs of AI writing*, maintained by the editors who clean up after it. It flags em
dashes and curly quotes, the structural shapes that survive paraphrasing, opinions attributed to
unnamed experts, summary sentences that restate what was just said. It also looks for signs of
*human* writing and says so when it finds none.

It deliberately does not flag the famous non-tells: perfect grammar, formal register, hedging,
transition words, the Oxford comma. Those are either listed as ineffective indicators or absent
from the guide entirely, and stripping them makes writing worse without making it more human.

If drafts do not sound like you, say so. The course profile carries a voice section, and that is
what to correct.

## Your student data

Several of these capabilities put real student records on your disk: downloaded submissions,
activity reports, rosters, a Gradescope export, an accommodations file. In the US these are
FERPA-protected education records; in the UK and EU they are personal data under GDPR. **You are
the data controller** for whatever lands on your machine, and your institution may impose stricter
rules about where it may be stored. Those govern.

Three rules the skills follow, and the first is enforced rather than encouraged:

1. **The cache directory is gitignored.** Before writing the first student file into a project, the
   skills check that `.gitignore` excludes `.canvas-cache/` and add it if not, and tell you they
   did.
2. **Nothing is transmitted without a specific request.** When something you asked for would move
   student data somewhere new, a shared drive, an email, an external service, Claude says plainly
   that it is student data and confirms first, even when the request is otherwise routine.
3. **Delete what you no longer need.** A submissions folder from an assignment graded three months
   ago is a liability with no remaining use.

Ask "what student data do I have on disk for 326" any time.

## The skills

| Skill | What it does |
|---|---|
| **course-setup** | Creates and inspects courses, connects platforms, builds and maintains the course profile. Everything else reads what this writes. |
| **syllabus** | Drafts, reviews, and edits the syllabus as a live LMS page; audits it against what the course actually does; rolls it into a new term; builds the syllabus quiz and the companion overview deck. |
| **lecture-decks** | Single-file reveal.js lecture decks with animated code diffs, morphing diagrams, an interactive slide, and speaker notes, sized to read from the back of a lecture hall. |
| **assignments** | Writes and reviews assignment specs, scopes them honestly, and catches ambiguity before students find it. |
| **student-questions** | Socratic replies to student questions, plus fetching unanswered Piazza threads, posting approved replies, and flagging public posts that leak assignment code. |
| **grading** | Rubric design, feedback drafting, evidence-backed scoring, grader consistency, regrade requests, and pushing approved scores to Canvas. Asks how far to go before starting. |
| **course-comms** | Announcements, deadline changes, corrections, exam logistics, and staff messages. |
| **course-reports** | End-of-term grade computation and auditing, and student activity and at-risk reporting. |
| **canvas** | The whole Canvas API surface. Other skills draft; this one posts. |

## Where things live

```
<courses root>/326/
├── .infra/                    tool state
│   ├── course.json            identity, and this course's layout convention
│   ├── course-profile.md      what the course teaches, its policies, its voice
│   ├── piazza/                config.json, credentials, inbox/, drafts/, actions.log
│   ├── canvas/                same shape
│   └── gradescope/            same shape
├── course/                    survives every offering
│   ├── units/  homework/  labs/  code/
│   └── slides/  videos/  reading/  drafts/
└── semesters/
    ├── current -> 2026-07-summer-2
    └── 2026-07-summer-2/      belongs to one run of the course
        ├── students/  grading/  accommodations/     gitignored
        └── announcements/
```

The split that matters: material that **survives the next offering** sits under `course/`, and
material tied to **one term** sits under `semesters/<term>/`. The question that decides it is
whether the thing would still be true if you taught the course again next year with different
students. A homework spec would. An accommodation letter would not. That is what makes rolling
over to a new term a new sibling folder rather than a copy-and-prune.

A registry at `~/.config/claude-courses/registry.json` records where each course lives, which is
what lets you say "326" instead of a path. It is an index, not a source of truth: delete it and
everything still works.

## Platforms, honestly

**Canvas** has a real, documented API. It is stable, it paginates properly, and it returns useful
errors. Anything that must actually land goes here, including grades that came from somewhere else.

**Piazza** has no public API. The client uses the unofficial `piazza-api` package against Piazza's
internal endpoints, so it can break. If your school logs into Piazza through SSO you may have no
Piazza password, and there is no workaround.

**Gradescope** has no public API either, and says so. The client scrapes their web app, where the
HTML parsing has broken about once a quarter while login and URLs stayed stable for six years.
Every selector fails loudly rather than returning nothing, because a gradebook full of silent nulls
is worse than a stack trace.

**Gradescope cannot be written to.** No maintained client implements score writing, Gradescope
documents no import path, and its data model computes scores from rubric selections rather than
point values. Rather than ship an endpoint that plausibly does nothing, this plugin has no
Gradescope write path at all. Grades go to Canvas.

**Google Workspace** (Drive, Calendar, Gmail) comes from account-level connectors, not from this
plugin. Nothing here needs configuring; if they are connected, the skills can use them.

## Credentials

Each platform's credentials live in `<course>/.infra/<tool>/credentials`, created at mode 600. Ask
Claude to check a course's setup and it complains if the permissions loosen or a key is blank.
Environment variables work as an override for someone teaching several courses on one account.

A Canvas token carries your full instructor permissions across **every** course your account
touches, not just this one. Canvas has no per-course tokens. Give it an expiry date and delete it
in Canvas when you stop using it.

## Under the hood

You do not need this section to use the plugin. It is here because knowing what runs is part of
trusting it, and because these are useful directly if you want them.

| Script | Purpose |
|---|---|
| `course_infra.py` | Owns the layout and the registry. `init`, `verify`, `layout`, `list`, `register`, `unregister`, `set-root`, `path`. |
| `prose_check.py` | Flags writing that reads as machine-generated. Runs before anything drafted is handed over. |
| `deck_check.py` | Structural checks on a reveal.js deck: the viewport override, auto-animate pairing, type sizing, self-containment, house style. |
| `canvas.py` | The general Canvas client: `get`/`post`/`put`/`delete`/`graphql` against any endpoint, with auth, pagination, rate-limit backoff, and the write gate. Every other Canvas script goes through it. |
| `canvas_api.py` | The curated Canvas client. Roster, assignments, submissions, grades, announcements, `whoami`, `undo`. |
| `canvas_common.py` | Shared helpers: the write gate, CSV loading, and the one roster-matching function they all use. |
| `sync_grades.py` | Imports a Gradescope or any CSV into a Canvas assignment, matched by email or SID, with a preview and a mismatch report. |
| `mark_late.py` | Marks genuinely-late imported work against each student's effective due date. Never auto-penalizes an accommodated student. |
| `late_penalties.py` | Applies a percent-per-day penalty or a semester late-day budget to already-graded work. |
| `rubric.py` | Creates Canvas rubrics from JSON and grades submissions by criterion name. |
| `upload_quiz.py` | Bulk-creates a Classic Quiz and all its questions from a JSON file. |
| `groups.py` | Creates group sets and populates teams from a roster mapping. |
| `download_submissions.py` | Downloads every submission for an assignment into per-student folders. Local only. |
| `cache_pages.py` | Caches Canvas page bodies locally. Local only. |
| `piazza_fetch.py` | Pulls unanswered Piazza threads. Read-only, safe to schedule. |
| `piazza_post.py` | Posts approved replies; privatizes public posts that leak code. |
| `gradescope_fetch.py` | Reads a Gradescope course: assignments, roster, scores, submissions. Read-only. |

`course_infra.py`, `prose_check.py`, `deck_check.py`, and every Canvas script are pure standard
library.

## Adding a platform

`course_infra.py` reads its whole notion of a tool from the `TOOLS` dict at the top of the file:
config keys, credential keys, and the regex that finds the platform's id in a course profile. Add
an entry and `init`, `verify`, and the credential loader pick it up with nothing else changed.
Write the client as a script next to the others, and have it call `resolve`, `load_config`,
`require_credentials`, and `log_action` so it behaves like the rest.
