# Why MangoMe?

MangoMe exists because long-running agent systems usually fail at the organizational layer before they fail at raw model capability.

The problem is not only whether a model can reason.

The problem is whether a system can preserve:

- identity;
- state;
- evidence;
- authority;
- verification;
- handoff;
- recovery;

across many sessions, tools, agents, models, and failures.

## Failure 1 — The agent forgot what it was doing

### Without MangoMe

```text
Session A performs work
    ↓
session disappears
    ↓
Session B reads repository + chat fragments
    ↓
reconstructs a plausible story
    ↓
continues from a guessed state
```

The repository may contain artifacts, but it does not necessarily contain the authoritative operational meaning of those artifacts.

### With MangoMe

```text
durable WorkIdentity
    +
canonical operational state
    +
unfinished work
    +
evidence / assurance history
```

A new worker recovers bounded canonical state instead of reconstructing the project from prose.

## Failure 2 — The agent resumed the wrong task

"ACTIVE" is not the same thing as "the user wants this continued now".

A system can have unfinished work while the current user asks a question, changes direction, or requests a different action.

### Without MangoMe

Recovered state can silently become execution permission.

### With MangoMe

```text
recovered state = context
current user turn = current intent
```

The two are reconciled before productive effect.

## Failure 3 — The agent said "done"

A worker can believe its implementation is complete and still be wrong.

### Without MangoMe

```text
worker: "done"
→ treated as success
```

### With MangoMe

```text
worker: "done"
        ↓
DONE_CLAIMED
        ↓
independent observation / evidence
        ↓
VERIFIED
        ↓
optional owner acceptance
        ↓
ACCEPTED
```

Execution and assurance are separate states.

## Failure 4 — Recovery became filesystem archaeology

A common agent pattern after losing context is:

```text
grep
find
Git history
old notes
old memory
contract folders
cached summaries
```

That can produce useful observations, but observations are not necessarily current authority.

### Without MangoMe

The worker may reconstruct a convincing but stale state.

### With MangoMe

For admitted work:

```text
canonical recovery first
    ↓
bounded unresolved delta
    ↓
targeted physical inspection
```

Filesystem and Git data validate or explain current work. They do not manufacture current identity.

## Failure 5 — The agent connected to the wrong database

This is especially dangerous because the system can look healthy while reading the wrong canonical state.

### Without MangoMe

```text
MCP process starts
MongoDB responds
→ "healthy"
```

but the selected database may be an eval database, stale environment, or another instance.

### With MangoMe

Runtime identity includes the intended database binding.

```text
MANGOME_DATABASE
MANGOME_EXPECTED_DATABASE
```

A mismatch fails closed instead of silently searching alternate databases for a state that "looks right".

## Failure 6 — Discovery accidentally became work

A user may only want to know what exists.

Example:

```text
discover /root/contracts
```

### Without a clear boundary

An agent can turn that into:

```text
scan
→ intake
→ restore
→ reconcile
→ import
→ mutate
```

### With MangoMe

Discovery is candidate-only observation.

```text
scan
→ candidates
→ return results
→ STOP
```

Admission is a separate explicit transition.

## Failure 7 — The coordinator escalated to expensive agents

A coordinator can convert a bounded task into a premium-model swarm simply because the task feels important.

That is not a reasoning problem. It is a governance problem.

MangoMe separates:

```text
worker identity
model identity
runtime mode
capability
cost class
authority
```

Runtime eligibility and delegation authorization are explicit decisions.

MangoMe does not itself dispatch providers. The external orchestrator must consume those decisions at the actual dispatch boundary.

## Failure 8 — The context became the memory system

Prompt context is temporary and bounded.

If the only durable state lives in the prompt, every compaction, session reset, provider change, or agent handoff risks epistemic loss.

MangoMe keeps canonical state outside the prompt and compiles only the currently useful projection into working context.

```text
persistent history
    ↓
active relevant state
    ↓
bounded execution context
    ↓
worker
```

The context is disposable. The operational record is not.

## The core distinction

MangoMe separates four things that agent systems often collapse:

```text
N = normative truth
    What should be true?

O = observed truth
    What is actually observed?

J = worker judgment
    What does the worker conclude?

V = independent verification
    What has been independently demonstrated?
```

A worker judgment can be useful without becoming truth.

An observation can be real without granting authority.

A completed implementation can exist without being verified.

A recovered state can exist without authorizing continuation.

These distinctions are the foundation of MangoMe.

## What MangoMe adds to an agent stack

A simplified stack looks like:

```text
Models / agents
      ↓
tools + MCP
      ↓
MangoMe
      ↓
durable work identity
canonical state
evidence
assurance
recovery
governed delegation
      ↓
repositories / services / external systems
```

MangoMe is deliberately model- and provider-neutral.

You can replace:

- the worker model;
- the orchestrator;
- the client;
- the playbook;
- the reasoning strategy;

without making the work itself disappear.

## Why this matters

The long-term goal is not to force agents into more bureaucracy.

It is the opposite:

> Do not constrain reasoning. Constrain truth mutation.

Workers should be free to inspect, reason, hypothesize, and adapt.

But durable organizational effects should have explicit identity, provenance, authority, and assurance.

That is the problem MangoMe is designed to solve.

## Next

- [Start Here](START_HERE.md)
- [Getting Started](getting-started.md)
- [Troubleshooting](troubleshooting.md)
- [Architecture](architecture.md)
- [Authoritative Recovery](authoritative-recovery.md)
- [Delegation Governance](delegation-governance.md)
