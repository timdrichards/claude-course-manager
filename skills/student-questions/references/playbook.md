# Playbook: archetypes worked through

Examples are from a web programming course, but the moves transfer. What matters is the shape of
the response, not the subject matter.

## Debugging: teach the diagnostic, not the fix

This is the most common archetype and the easiest one to get wrong, because you can usually see
the bug instantly and the fix is one line. Resist. The bug is disposable; the method for finding
it is the thing they keep.

The ladder, lowest rung first:

1. **Narrow the search space.** "Which of these two things is true: is the data wrong when it
   arrives, or does it arrive right and get mangled after? How could you find out?"
2. **Point at the observation they skipped.** "What does the network tab show for that request?"
3. **Make the wrong assumption testable.** "You're assuming the state has updated by the next
   line. What would you log to check that?"
4. **Name the concept.** "This is the classic stale-closure problem."
5. **Analogous example, different domain.**

Read what they already tried and start above it.

**Student post**
> My fetch works in the console but when I put it in my component the data is always empty. I've
> been at this for like 3 hours. Code below.
> ```js
> const [items, setItems] = useState([]);
> useEffect(() => { fetch('/api/items').then(r => r.json()).then(setItems); });
> console.log(items.length); // always 0
> ```

**Bad reply** — hands over the fix and the concept in one move, so the student learns "ask Piazza"
rather than "check when this runs":
> You're missing the dependency array, and your log runs before the fetch resolves. Change it to
> `useEffect(() => {...}, [])` and log inside the `.then`.

**Good reply**
> Three hours is rough, and the good news is your fetch logic is right. The problem is timing,
> not data.
>
> Add a log on the first line inside your effect and another right before `setItems`, then reload
> and read the console top to bottom. The order you see them in versus your `items.length` log is
> the whole story. What order do you get?
>
> Separately, watch how many times your effect log fires. That count will tell you something about
> the second bug.

It names what is working, aims at the assumption ("the data should be there by now"), gives them
a concrete action, and ends with a question. It also flags the missing dependency array without
saying what it is, since that is a second and separate thing for them to find.

## Conceptual: target the belief, not the topic

A conceptual question is a wrong mental model wearing a question mark. Find the model.

**Student post**
> I don't get why we need `await`. If the function returns the data why can't I just use it

The belief is "a function call produces its value by the time the next line runs," which is true
for everything they have written until now. Attacking `await` directly misses this.

**Good reply**
> Your instinct is right for every function you've written so far, so this is a fair thing to
> trip on.
>
> Here's the case that breaks it. Imagine ordering at a counter: you hand over your order and get
> a receipt, not a sandwich. The receipt is real and immediate, the sandwich is not. What could
> you do with a receipt, and what can you not do with it?
>
> Now look at what your function actually returns before the `await` — log it and see what type
> it is. Does the receipt idea match what you see?

The analogy is doing the work an explanation would do, and the log turns it into something they
verify rather than accept.

## Approach check: give them the criteria

"Is it okay if I..." usually means "I am about to spend six hours and I am scared." A grunt of
approval teaches nothing; withholding entirely is cruel.

Give them the criteria to judge by, and confirm viability if it is viable. Letting a student
burn a weekend on a dead end so they can discover it themselves is not a teaching win.

> That'll work, and it's a reasonable instinct. Before you build it, sketch what happens with
> 10,000 items and with duplicate keys, since those are the two cases that usually decide between
> your approach and the alternative. If it survives both, go.

When the choice *is* the assignment, say so plainly, because that is itself useful information:

> I can't tell you which one to pick here, since picking is most of what this assignment is
> testing. What I can tell you is what to compare on: lookup cost, insertion cost, and whether
> order matters for your output. Work each of those out for both options and the answer will be
> obvious.

## Close but wrong

The hardest case. The student has a mostly-correct model with one flaw, and a generic hint will
reinforce the flaw rather than expose it. Do not affirm the whole thing to be encouraging.

Name what is right, precisely, then aim a single question at the flaw:

> Steps 1 through 3 are exactly right. Step 4 assumes the list is still sorted after your insert.
> Walk through inserting 7 into `[1, 5, 9]` by hand with your code and see whether that holds.

The by-hand walkthrough is the workhorse move: it is the student doing the finding, on a case
small enough that the flaw cannot hide.

## Spec clarification: answer it

If the spec is genuinely ambiguous, that ambiguity is the course's fault. Answer directly, and
flag it in the note as something to clarify for everyone.

Watch for the design question hiding behind the clarification. "Does 'handle errors' mean I need
a try/catch?" is really "tell me how to structure my error handling." Answer what the spec
requires, stop there.

## Repeated questions

Three students asking the same thing is a signal about the lecture or the spec, not about the
students. Draft one canonical reply, note that it should be pinned, and mention what the pattern
suggests is missing upstream.
