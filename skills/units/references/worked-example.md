# Worked Example

One full unit, annotated: a lesson on idempotency from a web systems course.
Read the annotations as well as the content. They point at the specific moves
that make this a well-formed unit rather than merely correct prose.

The example follows the `knowledge-unit` preset. A course using a different
section contract still gets the useful part, which is what each section is
trying to do to the reader.

---

````markdown
# Unit 3: Idempotency, Delivery Semantics, and Data Consistency

## Introduction

Chapter 2 of the textbook frames distributed systems design as fundamentally
about anticipating failure. In a scalable web system, any HTTP call between
services can fail: the network drops a packet, the server processes a
request but the response never arrives, a connection resets mid-flight.
Chapter 2 introduces delivery semantics to describe what systems can
guarantee in those situations: at-least-once delivery ensures nothing is
silently lost but allows duplicates; at-most-once delivery prevents
duplicates but can lose requests entirely. Idempotency is what resolves that
tension. An operation that produces the same result whether it runs once or
ten times can safely use at-least-once delivery, because repeating it on
failure costs nothing.

Unit 2 measured how often calls fail. This unit asks what callers should do
about it. The intuitive answer is to retry until the call succeeds, but
without idempotency that is dangerous: if the server processed the request
and only the response was lost, retrying causes a duplicate effect. You will
watch this happen with a simulated payment API, then fix it with an
idempotency key, a design decision made before writing the first retry loop
that transforms retries from a source of corruption into a reliable
recovery mechanism.
````

**Annotation:** Paragraph 1 opens with the textbook chapter's own framing,
not "this unit is about idempotency" but the *problem* the chapter names.
Paragraph 2 opens by naming the previous unit's topic ("Unit 2 measured how
often calls fail") and stating precisely what's different now ("this unit
asks what callers should do about it"). It ends by previewing the concrete
artifact the student builds. No em-dashes anywhere in this section.

````markdown
## Before You Start

- Read: Designing Distributed Systems, Ch. 2

## References

- [`Map`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map)
- [Idempotency keys (Stripe)](https://stripe.com/docs/api/idempotent_requests)
- [`express.json()`](https://expressjs.com/en/4x/api.html#express.json)
- [HTTP status codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
````

**Annotation:** Before You Start lists only the source reading, no
placeholder line for a video or resource that doesn't exist yet. References
mixes a language feature (`Map`), a real-world API doc (Stripe), a
framework method (`express.json()`), and a general spec (HTTP status
codes), exactly the technical surface the unit's code touches, nothing
from the textbook.

````markdown
## Notes

### The starting problem

Here's a function that simulates charging a credit card. The network is
flaky: 30% of the time, the charge actually succeeds on the server, but the
response never makes it back to the client. From the client's point of
view, that looks exactly like a failed request, so the client retries.

```javascript
let totalCharged = 0;

const chargeCard = (amount) => {
  totalCharged += amount;
  const responseArrives = Math.random() > 0.3;
  if (!responseArrives) {
    throw new Error("timed out waiting for a response");
  }
  return { status: "charged", amount };
};

const chargeWithRetry = async (amount) => {
  for (const attempt of [1, 2, 3]) {
    try {
      return chargeCard(amount);
    } catch (err) {
      console.log(`Attempt ${attempt} failed: ${err.message}, retrying...`);
    }
  }
  throw new Error("all retries failed");
};

const main = async () => {
  await chargeWithRetry(20).catch(() => {});
  console.log(`Total charged: $${totalCharged}`);
};

main();
```

Run this a handful of times. Sometimes `totalCharged` is $20, like you'd
expect. Other times it's $40 or $60. The retry logic did exactly what you'd
want from a client that doesn't want to give up too early [...] but the
client and the true state of the world disagree, and the client has no way
to tell from the outside.
````

**Annotation:** This is beat 1. The code is under 30 lines, uses only
arrow functions and no classes (the course's JS-subset constraint), and its
bug (`Math.random() > 0.3` silently duplicating charges) is nondeterministic
by design, "run this a handful of times" is a direct instruction to
witness the flaw firsthand, not just read about it.

````markdown
### Extending the example

The fix isn't to retry less. It's to make the operation safe to repeat.
Give each logical charge a unique key [...]

```javascript
[... same chargeCard/chargeWithRetry structure, now taking an idempotencyKey
and checking a Map of processedKeys before charging again ...]
```

Run this several times. `totalCharged` stays at $20 no matter how many of
the three attempts time out, because the server recognizes the key on every
retry and hands back the result it already computed instead of charging
again.
````

**Annotation:** Beat 2 (here, "Extending the example", this unit has no
operational middle beat since it's a pure concept unit, not a tool-heavy
one). Same variable names, same function shapes as beat 1, a diff against
beat 1's code would be small and legible. The closing sentence explicitly
states the *new* invariant ("stays at $20 no matter how many... time out").

````markdown
### Naming the pattern

An operation is **idempotent** if doing it once and doing it five times
leave the world in the same state. [...]

This connects directly to **delivery semantics** [...]:

- **At-most-once:** [...]
- **At-least-once:** [...]
- **Exactly-once:** [...] often called **effectively-once** behavior [...]

Notice how this differs from the coordination problem in Unit 1. There,
multiple workers disagreed with each other about shared state. Here, it is
a single client and a single server that can disagree about whether
something happened [...]
````

**Annotation:** Beat 3/4. Every new term is bolded exactly once, at first
use (idempotent, delivery semantics, at-most-once, at-least-once,
exactly-once, effectively-once). The explicit backward reference to Unit 1
("Notice how this differs from...") is what keeps units from reading as an
isolated pile of topics, every unit's Naming beat reaches back to at least
one earlier unit.

````markdown
## Exercise

**Task:** Add a second, legitimate charge of $20 using a new idempotency
key (`"order-48214"`), then call `chargeWithRetry` for `"order-48213"` a
second time to simulate a client that didn't hear back and retried.

**Starting point:** The second code block in the Notes section above.

**You'll know it works when:** `totalCharged` reliably ends at $40 no
matter how many internal retries happen on either call. Add a one-line
comment explaining why the idempotency key, not the dollar amount, is
what determines whether two calls count as "the same" operation.
````

**Annotation:** The task is additive to the Notes code, not a fresh
scenario. "Starting point" points at a specific code block by position,
not a vague "build on what you did." The success condition is a literal
number ($40) plus a small reflective add-on (the comment) that checks
understanding, not just execution.

````markdown
## Real World

The Notes example runs entirely in memory. A real payment API uses the same
concept: the client sends an `Idempotency-Key` HTTP header with each
request, and the server deduplicates on it. This is exactly how Stripe
works.

Express is already set up from earlier units. [...]

```javascript
[Express server with a POST /charge route reproducing the same
idempotency-key logic over HTTP, using express.json() middleware]
```

```bash
npm init -y && npm pkg set type=module && npm install express
```

Start the server [...] and test it with two `curl` commands [...]
````

**Annotation:** One new tool (Express), reusing a tool already set up in
earlier units rather than introducing yet another framework. The exact
`npm install` line is given, not implied. The real-world example is
structurally identical to the Notes fix, same concept, HTTP instead of an
in-process function call.

````markdown
## Home Exercise

The server currently keeps processed keys forever. [...]

Add a `GET /history` endpoint [...]

```javascript
app.get('/history', (req, res) => {
  res.json(Object.fromEntries(processedKeys));
});
```

Then write a bash script `test.sh` that:

1. Sends the same charge three times with key `order-48213`
2. Sends one charge with a different key `order-48214`
3. Calls `GET /history` and prints the result

**You'll know it's working when** `/history` shows exactly two entries [...]
````

**Annotation:** Extends the Real World server specifically, not the Notes
code. Small enough to plausibly take under 30 minutes. Ends with the same
"you'll know it's working when" pattern as Exercise, and the student writes
their own verification script rather than being handed one.

````markdown
## Looking Ahead

Unit 6 moves from a single service's contract to a pair of cooperating
containers, the sidecar pattern, where the question shifts from "how do I
make one call safe to repeat" to "how do I add a capability to a service
without changing the service itself?"
````

**Annotation:** One paragraph. Names the next unit by number and topic, and
states the shift in framing precisely ("from X to Y") rather than a vague
"next we'll cover more patterns."
