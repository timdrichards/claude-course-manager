<!-- prose-check: reference -->

# Writing that does not read as generated

Everything this plugin drafts goes out under the instructor's name. A syllabus, an announcement,
a line of feedback on a student's work. If it reads as machine output, two things follow, and the
second is worse than the first: students discount it, and an instructor who tells students to
disclose their AI use has just failed to meet the standard they set.

So this is not a style preference. It is the credibility of the person whose name is on the file.

The tells below come from Wikipedia's **Signs of AI writing** (WP:AISIGNS), maintained by editors
who spend their days cleaning up after the thing they are describing. It is the most carefully
assembled list in existence, and it is gated: a word only goes in the vocabulary box if at least
one external corpus study documents the overuse.

Run the check before handing anything over:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prose_check.py draft.md
```

---

## Read this before the list

The guide is emphatic about three things, and they matter more than any individual tell.

**These are signs, not the problem.** In the guide's own words, do not "merely treat these signs
as the problems to be fixed; that could just make detection harder." Text that had every em dash
swapped for a comma and every "crucial" swapped for "important" is still generated text. The
problem is prose with no specific person behind it, and the tells are how that shows on the
surface. Fix the writing, not the symptoms.

**Several famous tells are not tells.** The guide lists these as *ineffective indicators*,
meaning they point at nothing or point the wrong way:

- Perfect grammar. Many people write well.
- Formal, academic, or "fancy" prose. The correlation is with *specific words*, not with register.
- Transition words on their own. "Furthermore" and "moreover" were demoted out of the tell list.
- Hedging and qualifiers. The guide lists hedges as a sign of *human* writing.
- Bland or robotic-sounding prose, which is a judgment about taste rather than an observation.
- The Oxford comma, non-breaking spaces, and en dashes. These circulate as folklore about the
  guide and appear nowhere in it.

Do not strip these out. Removing hedges and transitions to sound human produces prose that is
worse and no more human.

**Humans are bad at this.** Research the guide cites puts untrained human detection at roughly
chance. Heavy LLM users reach about 90%, which still means one false positive in ten. That cuts
both ways here: be suspicious of your own draft, and do not accuse a student's writing of being
generated on the strength of a word list.

---

## The character set

Absolute. These are house style, not statistics, and the checker flags every one.

**Em dashes.** Never. Use a comma, a period, or a semicolon. The guide notes that generated em
dashes are usually spaced ( — ), against normal typographic practice, and that the mark is used
where a human would reach for a comma, a colon, or parentheses. En dashes in number ranges
(`Units 8–11`) are correct and stay.

**Curly quotes and apostrophes.** Straight only. Curly marks arrive from smart-quote substitution
and mark text as pasted out of a chat window. (Worth knowing: the guide says Gemini and Claude
typically do *not* produce curly quotes, so their presence more often means Word or macOS
substitution than a chatbot. Fix them anyway; they are inconsistent within a document.)

**Emoji.** A course's deliberate title-prefix convention is fine and documented in
`house-style.md`. Decorative emoji on headings or bullets inside prose is a chatbot habit.

**Interface artifacts.** The return arrow `↩`, lenticular brackets `【 】` with a dagger,
`citeturn` markers, Private Use Area characters. Delete on sight. None of these are content.

**Assistant residue.** "As an AI language model", knowledge-cutoff disclaimers, "I cannot browse
the internet". This should never survive to a draft, let alone a reader.

---

## The strong tells

Each of these is a shape rather than a word, which is why they survive paraphrasing.

**Negative parallelism.** "Not just X, but Y." "It's not X, it's Y." "X rather than Y" as a
flourish. The construction implies you are correcting a misconception the reader never had. It is
the single most recognizable rhythm in generated prose.

> It's not just about the code; it's about the thinking behind it.

State the thing directly.

**Canned significance.** "Stands as a testament to." "Plays a crucial role in." "Underscores its
importance." "Enduring legacy." "Rich cultural heritage." "Evolving landscape." The guide's
diagnosis is exact: the model regresses to the mean, loses the specific fact, and compensates by
asserting importance louder. The result is "simultaneously less specific and more exaggerated."

When a draft insists something matters, the specifics went missing. Put them back and the
insistence becomes unnecessary.

**The trailing "-ing" clause.** A participle phrase glued to the end of a sentence, interpreting
it.

> The course uses a devcontainer, ensuring a consistent environment for all students.
> Enrollment reached 180 students, reflecting growing interest in the field.

These add the appearance of analysis and no information. Either the claim is real, in which case
it deserves its own sentence and a source, or it is filler. Cut it.

**The challenges formula.** A section that opens "Despite its [positive adjective], X faces
several challenges" and closes on a hopeful note, often beside a "Future Prospects" heading. The
guide is careful here: the tell is the rigid formula, not the mention of difficulty. Name the
specific difficulty and what is being done about it.

**Summary sentences.** "In summary." "In conclusion." "Overall." A paragraph that restates the
paragraph above it. A reader who got that far does not need the recap.

**Vague attribution.** "Experts argue." "Some critics have noted." "Industry reports suggest."
"Studies show." An invented consensus is worse than no claim, and in course material it is a
claim a student may repeat in an assignment. Name the source or cut the sentence.

**Canned notability.** "Independent coverage." "Profiled in." "Maintains an active social media
presence." Idiosyncratic to generated text and rare in human writing before 2024.

---

## The density tells

These are judgment calls. One instance is nothing; a pile in one document is among the strongest
signals available.

**Vocabulary.** The citation-gated list, strongest first: *delve*, *intricate/intricacies*,
*underscore*, *crucial*, *showcase*, *tapestry*, then *additionally* (sentence-initial), *align
with*, *emphasizing*, *enhance*, *fostering*, *garner*, *highlight*, *meticulous*, *pivotal*,
*boasts*, *bolstered*, *enduring*, *interplay*, *landscape*, *testament*, *valuable*, *vibrant*,
*robust*.

Take this literally. A word being overused does not make its synonyms suspect, so swapping
"crucial" for "essential" fixes nothing. Ask instead whether the word is carrying weight. Usually
one or two are and the rest are padding.

**Rule of three.** Three adjectives, or three parallel phrases, over and over. One triad is
ordinary English. A document where every list has exactly three items has a rhythm nobody chose.

**Copula avoidance.** "Serves as" for *is*. "Boasts" for *has*. "Features" and "offers" for *has*.
A documented decline in *is* and *are* in academic writing since 2023. The plain copula is listed
by the guide as a sign of human writing, so this is one to correct in both directions.

**Title Case headings.** Capitalizing Every Main Word. Use sentence case.

**Boldface.** Bolding every key term, or a bolded lead-in followed by a colon on every bullet.
Inherited from readmes, listicles, and slide decks. Bold the two or three things that matter.

---

## What human writing looks like

The guide's affirmative list, observed across 25 years of Wikipedia editing. Worth reading as
instructions rather than as a checklist.

- **Plain copulas.** "There is a", "it has a". Say *is* when you mean *is*.
- **Plain verbs over stiff synonyms.** *wrote* not *authored*, *moved* not *relocated*, *used*
  not *utilized*, *tried* not *attempted*, *died* not *passed away*. The plain word is the human
  tell and the euphemism is the machine one, which is the reverse of what people assume.
- **Definite claims.** "One of the best", "is the only", "was the first". Generated text hedges
  its way out of commitment. A person who knows the subject will say a flat thing.
- **Ordinary hedges.** *very*, *perhaps*, *tends to*, *roughly*. These are human, not machine.
- **Wordy constructions.** "As a result of", "in order to", "the fact that". Not elegant, and
  that is the point: real writing has slack in it.

Two more that are not on the guide's list and matter for course material:

- **Specifics that could only come from this course.** The number of students, the thing that
  went wrong last term, the name of the tool, the fact that the deadline is Sunday because Monday
  is when the autograder is rebuilt. Generated prose is smooth because it has nothing particular
  in it.
- **A real opinion, held by a person.** "I strongly advise against pairing this course with full
  time work." A sentence that takes a position and accepts a consequence cannot be written by
  averaging a corpus.

---

## The revision pass

Before any draft is handed over:

1. **Read it aloud, in your head, as the instructor.** Anything they would not say gets cut. This
   catches more than the checker does.
2. **Run the checker.** Fix everything in the character set. Judge the rest.
3. **Ask what is specific here.** If a paragraph would be equally true of any course at any
   university, it is filler and it should either gain a detail or go.
4. **Check the ending.** Generated text almost always ends by summarizing or reaching for uplift.
   Stop at the last real sentence.

The last one is the highest-yield edit available and it takes five seconds.
