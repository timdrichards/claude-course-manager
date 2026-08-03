# The syllabus quiz

A short, low-stakes quiz over the syllabus, given in week one. Its purpose is not assessment. It
is that students who have answered a question about the late policy cannot later say they did not
know it, and that the instructor finds out in week one which sentences are unclear rather than in
week six from the same question asked eleven times.

---

## What to ask about

Target the sections that generate the most email. In practice that is:

- **Late work.** The arithmetic and the cutoff, on a concrete case. "You submit Homework 2 thirty
  hours after the deadline. What happens?" is a better question than "What is the late policy?"
- **What the late policy does not cover.** If sprints have hard deadlines, ask about a sprint.
  This is the single most valuable question on the quiz.
- **AI use.** One question on something permitted and one on something not. Use the syllabus's
  own examples.
- **Disclosure.** What a student must include when they used AI.
- **Communication.** The subject-line convention, if the course has one, and where questions go.
- **Submission mechanics.** Which platform for which kind of work, and which attempt is graded.
- **Grading weights.** One question on the largest category.
- **Something term-shaped.** In a compressed term, the weekly hour expectation. Students who
  answer this in week one and are surprised in week three at least chose knowingly.

Eight to twelve questions. Long enough to cover what matters, short enough that students actually
read the syllabus rather than guessing.

## What not to ask

- Anything not answerable from a specific sentence in the syllabus. Every answer must be
  checkable, and writing the quiz is itself an audit: a question you cannot ground in a sentence
  means the syllabus does not say what you thought.
- Trivia. The instructor's office number teaches nothing.
- Trick questions. The goal is that they read it, not that they fail.
- Anything the syllabus states ambiguously. Fix the syllabus first, then write the question.

## Settings

Low stakes and generous: a small point value, unlimited or many attempts, keep highest, no time
limit. A student retaking it until they get everything right has done exactly what the quiz is
for. Make it a practice quiz or a small graded quiz depending on whether the course wants it in
the gradebook.

**Classic Quizzes only.** New Quizzes cannot export per-student answers through the API, which
means nobody can later check what a student was actually told they answered.

---

## The bank format

`upload_quiz.py` takes a JSON file with a `quiz` object and a `questions` array, and creates the
quiz and every question in order.

```json
{
  "quiz": {
    "title": "✔️ Syllabus Quiz",
    "description": "<p>A short check that you have read the syllabus. Retake it as many times as you like; your highest score counts.</p>",
    "quiz_type": "assignment",
    "points_possible": 10,
    "allowed_attempts": -1,
    "scoring_policy": "keep_highest",
    "shuffle_answers": true,
    "published": false
  },
  "questions": [
    {
      "question_name": "Late homework",
      "question_text": "<p>You submit Homework 2 thirty hours after the deadline. What score can you receive at most?</p>",
      "question_type": "multiple_choice_question",
      "points_possible": 1,
      "answers": [
        {"answer_text": "80% of the points you earned", "answer_weight": 100,
         "answer_comments": "Two days late means two 10% deductions."},
        {"answer_text": "90%", "answer_weight": 0},
        {"answer_text": "Full credit, it is within the grace window", "answer_weight": 0},
        {"answer_text": "Zero, it is past the deadline", "answer_weight": 0}
      ]
    },
    {
      "question_name": "Sprint deadlines",
      "question_text": "<p>Sprints can be submitted late for a per-day deduction, the same as homework.</p>",
      "question_type": "true_false_question",
      "points_possible": 1,
      "answers": [
        {"answer_text": "True", "answer_weight": 0},
        {"answer_text": "False", "answer_weight": 100,
         "answer_comments": "Sprints have hard deadlines. Your team depends on the work being in place."}
      ]
    }
  ]
}
```

**Fields that matter:**

- `answer_weight` is `100` for correct and `0` for incorrect. Exactly one answer at 100 for a
  multiple choice question.
- `answer_comments` is shown to the student after they answer. Use it. This is where the quiz
  stops being a checkbox and starts teaching, and it is the reason a wrong answer is useful.
- `allowed_attempts` of `-1` means unlimited.
- `quiz_type` is `assignment` for a graded quiz, `practice_quiz` for one that does not enter the
  gradebook.
- `published` stays `false`. Publishing is a separate, approved step.

Useful `question_type` values: `multiple_choice_question`, `true_false_question`,
`multiple_answers_question`, `short_answer_question`, `matching_question`. Prefer multiple choice
and true/false; short answer requires manual grading, which defeats the point of a week-one quiz.

---

## Creating it

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/upload_quiz.py syllabus-quiz.json --course 326 --dry-run
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/upload_quiz.py syllabus-quiz.json --course 326 --live
```

The uploader stops at the first failed request rather than continuing, so a partial failure is
reported rather than papered over. It records the created quiz in the course's `actions.log`.

Save the bank JSON into the course folder. Next term's rollover starts from it, and a question
that turns out to be ambiguous is worth fixing in a file rather than rediscovering.

---

## What the results tell you

Read the item analysis after the deadline, not just the scores.

A question most of the class gets wrong is not a class that did not read. It is a sentence in the
syllabus that does not say what its author thinks it says. Fix the syllabus, announce the
correction, and keep the question.
