# How I work

Principles I actually apply, each with the decision in this repo that demonstrates it.
Stated as trade-offs rather than virtues, because every one of them costs something.

---

## Ship the boring version first

Production runs Docker Compose and Celery on VMs, not Kubernetes. At the current tenant
count the operational cost of a cluster was not justified by the scaling benefit, and
adopting it early would have bought complexity paid for daily against a scaling problem
that had not arrived.

What makes this a decision rather than an omission is that **the migration is designed and
the trigger is written down** — the manifests, the probe strategy and the autoscaling
signal all exist ([`reliability/k8s/`](reliability/k8s/)), along with the condition that
should make us adopt them.

Choosing *not* to adopt something deserves the same written reasoning as choosing to.

> **Cost:** we will migrate under more time pressure than if we had done it early.
> Accepted, because the alternative is paying for a cluster's operational overhead through
> every sprint in between.

---

## Decide what the system is not allowed to do

In the invoice pipeline, GL account selection is deliberately left manual. It is
technically the easiest field to predict — strongly correlated with vendor and description,
and a model would score well on it.

It stays manual because it is **accounting judgement, not extraction**. The same expense can
land in different accounts depending on capitalisation policy, period and treatment
decisions that live in a finance team's heads and change. High accuracy on a judgement call
produces confident, plausible, wrong postings — the most expensive kind of error, because
nobody reviews what looks right.

The same instinct appears in the governance framework's *never automated* column, and in
the support agent's privilege veto. Knowing where to stop is most of the design.

> **Cost:** a lower automation rate, and a demo that looks less impressive.

---

## Make failure detectable rather than impossible

You do not eliminate hallucination. You make it **detectable, bounded, and cheap to fail
on** — grounded retrieval, citation coverage, an approved-claims allow-list, a groundedness
check on the way out, and a human gate for the cases that fail them.

The design question is not "how do we stop it being wrong" but **"what does it do when it
doesn't know?"** Guessing is the actual bug. Every system here has an abstain path.

---

## Constrain the output space instead of instructing the model

*"Never make unapproved health claims"* in a system prompt is guidance. Requiring every
claim to be retrievable from an approved-claims collection is a gate.

The inversion matters: detecting bad claims is open-ended and **fails open**; permitting
only known-good ones is closed and **fails shut**. Where a mistake has legal consequences,
the control has to be structural.

> **Cost:** somebody has to maintain the allow-list, and an out-of-date list silently
> blocks legitimate copy.

---

## Put isolation where it cannot be forgotten

The common design puts a tenant filter in the query the application builds. That works
until one code path omits it — and the bug is silent, because the caller gets *more*
results rather than an error.

So the retriever is constructed with a tenant and applies the predicate itself. There is no
parameter with which to widen the scope ([`reliability/governance-layer/`](reliability/governance-layer/)).
The same reasoning applies to fetch-by-id, which is where the scoped-search-plus-unscoped-detail-view
bug usually lives.

**Isolation you can forget to apply is not isolation.**

---

## Choose the tool per question, not per project

One pipeline can legitimately use a language model, a fuzzy match and plain arithmetic.

*"What does this invoice say?"* is genuinely ambiguous — a model is right. *"What is this
vendor's code?"* has exactly one correct answer sitting in a database table — a deterministic
lookup is right, and a vector search is how you get a hallucinated vendor code.

Most hallucination risk is removed by **not asking the question**.

---

## Test the failure, not the happy path

Every module here is tested by inducing the failure it exists to handle: the breaker is
driven open and probed, a worker is killed mid-run to prove the resume skips completed
steps, an injection is fired at the guardrail, an audit entry is tampered with to prove
verification breaks.

A guardrail verified once by hand is a guardrail that quietly stops working on the next
prompt change. Adversarial cases belong in CI, at a **blocking** threshold — which is why
the gates are tiered by consequence rather than blended into one pass rate.

---

## Say what is built and what is designed

Everything in this repo carries a maturity label. 🟢 carries live traffic, 🔵 is built and
tested but not deployed, ⚪ is designed only.

Labelling is not modesty — it is the thing that makes the rest of the document worth
reading. A portfolio where everything is implied production collapses under one probing
question, and takes the genuinely true claims down with it.

---

## Write the decision down, including what you would change

Architecture decisions live in [`platform/decisions/`](platform/decisions/) in a fixed
shape: context, options considered, decision, consequences, and **what I would revisit at
10x scale**.

That last section is the one that matters. A decision recorded without its expiry
conditions becomes folklore — the next engineer inherits the conclusion without the
reasoning, and cannot tell whether it still holds.
