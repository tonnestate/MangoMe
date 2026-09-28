# Start Here — MangoMe

MangoMe is a persistent operating layer for long-running AI-agent work.

If an agent session disappears, a model changes, a task is resumed later, or several agents work on the same system, MangoMe keeps the operational state outside the chat. It records what the work is, what is expected, what has been observed, what was claimed, and what has actually been verified.

You do **not** need to learn MangoMe's internal vocabulary before using it.

## MangoMe in 60 seconds

Without MangoMe, an agent often reconstructs work from:

- chat history;
- repository files;
- stale notes;
- filenames;
- remembered assumptions;
- whatever context happens to be loaded.

With MangoMe, the intended flow is:

```text
User request
    ↓
Agent understands the task
    ↓
MangoMe reconciles durable work state before productive effects
    ↓
Agent executes
    ↓
Progress and evidence are persisted
    ↓
DONE remains a claim
    ↓
Verification remains separate
```

The important idea is simple:

> Agents may forget. The work should not.

## What MangoMe is

MangoMe provides:

- durable work identity across sessions and agents;
- canonical operational state;
- plans and execution state;
- evidence and provenance;
- explicit verification and acceptance states;
- safe recovery after session loss;
- controlled discovery of existing artifacts;
- runtime and delegation governance for external orchestrators;
- bounded context projection for agents.

## What MangoMe is not

MangoMe is **not**:

- an LLM;
- an agent model;
- a replacement for Git;
- a replacement for MongoDB;
- a general model router;
- a provider-specific agent framework;
- a guarantee that an agent is correct;
- a mechanism that turns a worker's "done" statement into verified truth.

It is infrastructure underneath agent work.

## The beginner mental model

You only need four concepts at first:

```text
WORK
  What are we trying to do?

STATE
  Where are we now?

EVIDENCE
  What was actually observed?

VERIFICATION
  Has an independent check demonstrated the claim?
```

More advanced MangoMe concepts such as `WorkIdentity`, `NormativeBaseline`, `WorkTurn`, `PCH/1`, `SRA/1`, `BTTM/1`, `FJD/1`, `MTB/1`, and `UAI/1` exist, but you do not need them to get started.

## Install

Requirements:

- Python 3.10+
- MongoDB for canonical production persistence
- a supported agent client such as Codex or Claude Code

From the MangoMe repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

For canonical local MongoDB persistence:

```bash
export MANGOME_BACKEND=mongo
export MANGOME_MONGODB_URI='mongodb://127.0.0.1:27017'
export MANGOME_DATABASE='mangome'
```

Then configure supported clients:

```bash
mangome setup --client auto
```

## Check that MangoMe is healthy

Run:

```bash
mangome health
```

For a normal local MongoDB setup, the important fields are:

```text
process_ready = true
database_ready = true
database_binding.database = mangome
database_binding.state = BOUND
```

If that is not true, do not start debugging by searching old agent memory or old project files. See [troubleshooting.md](troubleshooting.md).

## Check the client integration

For Codex:

```bash
mangome attest-client codex
```

For Claude Code:

```bash
mangome attest-client claude-code
```

You can also run:

```bash
mangome doctor
```

and, when the managed configuration is safely repairable:

```bash
mangome doctor --repair
```

## Your first normal task

You do not need a MangoMe-specific prompt.

For example:

```text
Review this module, find the bug, fix it, and test the change.
```

The agent may inspect and reason freely. Before the first productive effect, MangoMe reconciles the assignment with durable state. Existing work is reused when possible; genuinely new work is admitted as new work.

You should not need to manually create MangoMe contracts, plans, slices, or recovery objects.

## Your first resume

A later session can simply continue the work in normal language.

MangoMe should recover the relevant durable work identity and unfinished state. It must **not** reconstruct current truth from stale host memory, old agent prose, broad filesystem archaeology, or Git history.

If recovery returns `STATE_NOT_FOUND`, that is a real signal. MangoMe must not manufacture replacement state and call it restored.

## Your first discovery

Discovery is intentionally different from normal work.

Example:

```text
discover /root/contracts
```

Expected behavior:

```text
one bounded candidate scan
    ↓
candidate results
    ↓
STOP
```

A discovery-only request must not automatically:

- create work;
- run `intake_request`;
- run assignment reconciliation;
- restore a project;
- reconcile all discovered candidates;
- admit candidates into canonical truth.

Discovery observes. Admission is separate.

## Where to go next

- [Getting Started](getting-started.md) — complete first installation and workflow.
- [Troubleshooting](troubleshooting.md) — common failure codes and what they mean.
- [Why MangoMe](WHY_MANGOME.md) — concrete failure modes MangoMe is designed to prevent.
- [Assignment Reconciliation](assignment-reconciliation.md) — deeper explanation of the effect boundary.
- [Authoritative Recovery](authoritative-recovery.md) — how recovery avoids filesystem reconstruction.
- [Big-Bang Import](bigbang-import.md) — discovery and candidate reconciliation.
- [Delegation Governance](delegation-governance.md) — runtime capability and external dispatch policy.
- [Architecture](architecture.md) — deeper system architecture.

---

MangoMe's internal machinery is intentionally more rigorous than its user interface. Start with work, state, evidence, and verification. Learn the deeper layers only when you need them.
