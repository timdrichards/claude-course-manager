---
name: assignments
description: >
  Write, revise, and audit assignment specs, project descriptions, starter code plans, and the
  rubrics that go with them. Use when the user says "write an assignment", "draft the spec for
  homework 3", "revise this assignment", "is this spec clear", "students keep misreading this
  assignment", "scope this project", "what should the starter code look like", "turn this into a
  Canvas assignment", or hands over a draft spec for review. Also use when student questions
  reveal a spec is ambiguous and it needs fixing for everyone. Do NOT use for syllabi, which is
  the syllabus skill, for grading submissions, which is the grading skill, or for answering an
  individual student's question about an assignment, which is student-questions.
---

# Assignments

An assignment spec is read by every student in the course, under time pressure, without the
author present to clarify. Ambiguity in it does not stay ambiguous; it becomes forty variations
of the same Piazza question and a grading batch where nobody scored the same thing.

## Start from the course, not from a blank page

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/course_infra.py verify 326
```

Load `.infra/course-profile.md`. It says what has been covered, what has not, what the course
deliberately withholds, and how the instructor writes. An assignment that requires a concept
three weeks out is not hard, it is broken, and the profile is what catches that before students
do.

Read the syllabus too, or ask for it. Late policy, collaboration policy, AI use policy, and
submission mechanics all get referenced by the spec, and a spec that contradicts the syllabus
creates a dispute the instructor loses.

If either is missing, say so and offer to set them up rather than inventing policy. A spec that
states a late policy the course does not have is worse than one that omits it.

## The one question to answer first

**What must a student be able to do at the end that they could not do at the start?**

Everything else follows from that. The skill under test determines what the assignment can hand
them, what the starter code includes, what the rubric measures, and what hints staff can give
when they get stuck. An assignment without a clear answer to it tends to become a pile of
requirements that is laborious rather than instructive.

Ask for it if the user has not said. "Practice with React" is a topic, not a skill. "Decide when
state belongs in a component versus lifted up, and implement both" is a skill, and it tells you
immediately that the starter code must not pre-place the state.

Everything the assignment gives away is something it cannot test. Write the rubric and the
starter code against that single sentence.

## Structure

Read `references/spec-anatomy.md` for the full treatment. The short version, in the order
students read:

1. **What you are building**, in two or three sentences, concretely. A student should be able to
   picture the finished thing.
2. **Why**, in one sentence, tied to the skill under test. Students work harder on assignments
   whose point they understand, and it is usually true and rarely said.
3. **Requirements**, numbered, each independently checkable. Numbered because Piazza questions,
   rubric items, and regrade requests will all cite them.
4. **Constraints**: what is required, forbidden, or provided. Say why for anything forbidden. A
   rule with a reason gets followed; a rule without one gets treated as arbitrary and worked
   around.
5. **Getting started**: repo, starter code layout, how to run it, how to run the tests.
6. **Submission**: exactly where, exactly what, exactly by when, in the course's timezone.
7. **Grading**: the rubric, or a pointer to it, and how partial credit works.
8. **Where to get help**: office hours, the forum, and what staff will and will not tell them.

## Requirements that survive contact with students

Each requirement should pass three tests:

- **Checkable.** Could a grader decide unambiguously whether it is met? "Handle errors
  gracefully" fails. "A failed network request shows a retry option and does not clear the
  form" passes.
- **Singular.** One requirement, one thing. Compound requirements produce partial completions
  that no rubric anticipated.
- **Necessary.** Is it teaching the skill under test, or is it there because it seemed
  thorough? Every extra requirement costs student time that comes out of the part that matters.

Write the rubric at the same time as the requirements, not afterward. Anything that cannot be
turned into a rubric item is not really a requirement, and discovering that while writing the
spec is much cheaper than discovering it while grading. Read
`${CLAUDE_PLUGIN_ROOT}/skills/grading/references/rubrics.md` when writing one.

## Scope

Scope estimates are systematically wrong in one direction: an assignment takes students roughly
three to five times what it takes the person who wrote it, and more when the setup is unfamiliar.
The author knows the design, has the environment working, and does not spend two hours on a
dependency error.

Say the expected hours in the spec, and be honest about it. Students plan against it, and a spec
that claims six hours for fifteen hours of work produces late submissions and a mid-semester
collapse in trust.

Ways to cut scope that preserve the learning: give away setup and boilerplate in starter code,
provide the test harness, narrow the feature set rather than the depth, and cut the third
instance of something they already demonstrated twice. Ways that do not: removing the design
decisions, or replacing them with a prescribed structure. That is the assignment.

## Reviewing an existing spec

When handed a draft, read it as an anxious student at 11pm and report what is genuinely unclear.
Group findings:

- **Ambiguities**: a requirement two careful readers would implement differently. These are the
  expensive ones; each becomes a Piazza thread and a grading inconsistency. Quote the sentence
  and give the two readings.
- **Contradictions**: with the syllabus, with the rubric, with itself, or with the starter code.
- **Gaps**: a requirement with no way to know it is done, a submission process not stated, a
  deadline without a timezone, a dependency on something not yet taught.
- **Giveaways**: a spec so prescriptive that the skill under test has been handed over.
  Requirements listed in implementation order often do this without meaning to.
- **Scope**: where the stated time and the real work diverge.

Lead with the ambiguities. They cost the most and are the cheapest to fix before release.

**When a spec problem is discovered mid-assignment** because students are asking about it, the
fix is a clarification to everyone rather than an answer to whoever asked. Draft it as a
correction: what was unclear, what it means, and whether anything about the deadline or grading
changes as a result. Hand it to course-comms to send.

## Publishing

Assignment text is markdown; Canvas takes HTML. Convert before posting, and check tables and
nested lists specifically.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas_api.py --course 326 \
    create-assignment --file spec.json --live
```

Leave `published` false unless asked. A published assignment is visible immediately, and one that
appears and then changes three times costs more student confidence than a day's delay does. In a
course with weighted assignment groups, set `assignment_group_id`; without it the assignment
lands in the default group and quietly changes the weighted-grade math.

Save the spec into the course folder as well, so grading and student-questions can read what
students were actually told rather than a paraphrase of it.

## Before handing it over

Everything drafted here goes out under the instructor's name, so it has to read as theirs and not
as machine output. This step is required, not advisory.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py draft.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py --text "the paragraph"
```

Fix everything labelled `FIX`. Fix `STRONG` findings too, unless there is a reason to keep one,
and then say the reason out loud rather than leaving it silent. `REVIEW` findings are judgment.

Then do the part no checker does: read it as the instructor would say it, cut anything they would
not, and stop at the last real sentence instead of summarizing. Generated text almost always ends
by reaching for a summary or for uplift, and deleting that ending is the highest-yield edit
available.

Read `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md` before rewriting anything
to sound more human. Several famous "AI tells" are not tells at all, and stripping out hedges and
transitions produces prose that is worse and no less synthetic.

## References

- `references/spec-anatomy.md`: each section of a spec, what belongs in it, worked examples of
  vague versus checkable requirements, and how starter code and the skill under test constrain
  each other.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/house-style.md`: voice and
  formatting, shared with every drafting skill in this plugin. The course profile's
  `Voice` section overrides it.
- `${CLAUDE_PLUGIN_ROOT}/skills/course-setup/references/ai-tells.md`: the tells that
  make writing read as generated, what human writing looks like instead, and the
  famous "AI tells" that are not. Read before rewriting prose to sound more human.
