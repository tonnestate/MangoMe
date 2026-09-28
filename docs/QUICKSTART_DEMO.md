# MangoMe — 5-minute demo

This is the shortest path from a fresh checkout to a visible MangoMe integration.

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 2. Smoke-test without MongoDB

```bash
export MANGOME_BACKEND=memory
mangome health
```

Configure one client:

```bash
mangome setup --client codex --backend memory
```

or:

```bash
mangome setup --client claude-code --backend memory
```

Then attest the binding:

```bash
mangome attest-client codex --backend memory
```

## 3. Observation-only test

Ask the agent:

```text
Use MangoMe. Discover this repository and summarize the candidate files. Do not modify anything.
```

Expected control flow:

```text
observation
→ one bounded discovery
→ candidate result
→ STOP
```

Discovery must not silently create admitted work.

## 4. Productive-work test

Ask for one small real change in a disposable file.

Conceptually MangoMe should perform:

```text
understand
→ reconcile before effect
→ execute bounded work
→ DONE_CLAIMED
→ validation
→ independent verification
→ CLOSED when required effects are reconciled
```

## 5. Durable MongoDB mode

For state that must survive process restarts:

```bash
export MANGOME_BACKEND=mongo
export MANGOME_MONGODB_URI='mongodb://127.0.0.1:27017'
export MANGOME_DATABASE='mangome'
mangome health
```

A normal local production binding should report database `mangome`, not the legacy evaluation database.
