# Anatomy of an assignment spec

Each section, what belongs in it, and the failure it prevents.

---

## What you are building

Two or three sentences, concrete enough that a student can picture the finished artifact. Screens,
inputs, outputs, behavior. Not "you will explore state management in React" but "you will build a
shopping cart that persists across page reloads and correctly handles adding an item that is
already in the cart."

The failure this prevents: a student who reads the whole spec and still does not know what they
are making, and therefore cannot tell whether they are on track.

## Why

One sentence tying it to the skill under test. "This is the first assignment where the state
lives in more than one place, which is the situation lifting state exists to solve."

Optional in form, valuable in effect. Students work harder on assignments whose point they
understand, and the sentence usually already exists in the author's head.

## Requirements

Numbered. Always numbered, even when there are three, because every downstream artifact will cite
them: the rubric, Piazza answers, regrade requests, and the clarification announcement sent in
week two.

Each requirement independently checkable and singular. The comparison that makes this concrete:

| Vague | Checkable |
|---|---|
| Handle errors gracefully | A failed request shows a retry option and leaves the form contents intact |
| The UI should be responsive | Layout is usable at 375px wide with no horizontal scroll |
| Validate the input | Reject an empty name, a quantity below 1, and a non-integer quantity, each with a distinct message |
| Use good component structure | No component both fetches data and renders a list; separate them |
| Write tests | At least one test per public function in `cart.js`, including the empty-cart case |

The right-hand column is longer. That is the cost, and it is much smaller than the cost of forty
students implementing the left-hand column five different ways.

Requirements that describe *implementation* rather than *behavior* are a specific hazard: they
often hand over the design decision that was the assignment. "Create a `reducer` function that
takes state and an action" has just made the interesting choice for the student. If the structure
genuinely must be prescribed, say why, and accept that the rubric can no longer measure that
choice.

## Constraints

What is required, forbidden, or provided, and **why** for anything forbidden.

The reason matters more than instructors expect. "Do not use a library for this" reads as
arbitrary and gets treated as a rule to route around; "do not use a date library, because parsing
the format yourself is what this assignment is teaching" gets followed, and it answers the Piazza
question before it is asked. Students are not trying to cheat when they ask why a rule exists;
they are trying to understand a decision.

State constraints on: libraries and frameworks, language features, external services, starter
code that must not be modified, and collaboration. Point at the syllabus for collaboration and AI
policy rather than restating it, unless this assignment differs, in which case say so loudly
because a per-assignment exception to a course policy is exactly what gets missed.

## Getting started

Repo or starter code location, its layout, how to install, how to run it, how to run the tests.

The starter code is a design decision, not a convenience. Everything it provides is something the
assignment cannot test, and everything it omits is time students spend on setup instead of on the
skill. Two rules:

- **Give away everything that is not the skill under test.** Build config, boilerplate, styling,
  test harness, fixtures. A student debugging a webpack config is learning something, but not the
  thing being graded.
- **Give away nothing that is.** If the assignment tests whether they can choose a data
  structure, the starter must not declare one. If it tests component decomposition, the starter
  must not ship the component tree.

Include one worked example of running it end to end with expected output. The single most common
first Piazza question on any assignment is some version of "I cloned it and I don't know if it's
working."

## Submission

Exactly where, exactly what, exactly when, with day of week and timezone. "Friday, October 9 at
11:59pm ET on Gradescope, as a zip containing `src/` and `README.md`."

Include what happens if they submit late, or point at the syllabus policy. Include whether
multiple submissions are allowed and which one counts, because on any assignment with an
autograder someone will submit thirty times.

## Grading

The rubric, or a link to it, plus how partial credit works. Publishing the rubric is worth it:
students optimize for it, which is the rubric doing its job, and it converts "why did I lose
points" into "which item", which is answerable in one sentence.

If part of the grade is an autograder, say what it checks and what it does not, and say whether
its partial credit matches the rubric's. A student who passes every visible test and scores 70%
without warning has a legitimate complaint.

## Where to get help

Office hours, the forum, and, the part usually omitted, **what staff will and will not tell
them**. "We will help you understand an error message or a concept; we will not debug your code
line by line or tell you which approach to take." Setting that expectation in the spec makes
every forum interaction easier for the whole term, and it makes a Socratic reply feel like policy
rather than like being stonewalled.

---

## Two failure patterns worth naming

**The spec that is really a tutorial.** Requirements listed in implementation order, each one a
step, so that following them produces the solution. It generates high completion and low
learning, and it is usually the result of writing the spec by describing the reference solution.
Write requirements as properties of the finished thing, not as steps.

**The spec that grew.** Each term adds a clarification, and after three years the assignment has
fourteen requirements, four of which contradict the starter code. When reviewing an inherited
spec, ask which requirements are still teaching something, and cut rather than clarify.

## After release

The spec is a document students plan against, so changing it has a cost. Corrections during the
assignment window need to go to everyone, not just whoever asked, and they should say plainly
whether the deadline or the grading changes as a result. Hand that to the course-comms skill.

Keep the released version in the course folder. Grading and student-questions need to know what
students were actually told, and a spec edited in place makes that unknowable.
