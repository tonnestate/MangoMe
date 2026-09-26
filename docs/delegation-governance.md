# Delegation and Runtime Capability Governance

MangoMe treats model delegation as governed execution state rather than an informal coordinator choice. This applies to every MangoMe-governed workstream, not only recovery.

The motivating failures were concrete:

1. a recovery coordinator reconstructed admitted work through broad repository/path discovery instead of reading canonical MangoMe state; and
2. the same recovery line dispatched **five high-cost agents** during one recovery session although the requested reconstruction work was bounded and cheap/mechanical; four completed and one was stopped with its checkpoint preserved.

The incident also established an important boundary: the inspected MangoMe repository did not contain the provider/model spawn call. A disconnected guard inside MangoMe would therefore be policy theater rather than dispatch enforcement.

The second failure requires a different control surface from authoritative recovery. Fan-out width and model tier are independent: broad cheap/standard fan-out can be valid while premium escalation remains explicitly authorized. Recovery determines **where state comes from**. Delegation governance determines **which runtime is eligible to act on any bounded delta**. Live tests showed the same escalation tendency across different parent agents, so model prestige, task importance, difficulty, urgency, or a capability gap must never imply permission to spawn a stronger/high-cost worker.

## Separate identity from capability

MangoMe deliberately separates:

```text
worker identity
model identity
runtime mode
current capabilities
cost class
authority
```

A model name is not a capability grant. A provider may move a logical model into a reserve/degraded mode while keeping the same model identity. A runtime that could deploy earlier may later be able to read/reason/test but no longer deploy.

The current host-observed runtime profile therefore controls eligibility.

## Current capability, not historical capability

The host/router publishes a runtime snapshot containing:

```text
worker_key
model_id (optional)
runtime_mode
capabilities
cost_class
owner_gated
max_parallel_tasks
active
```

The snapshot is host-observed state. It is not a worker self-report.

MangoMe exposes `publish_worker_runtime` through a separate router capability. A normal worker must not possess the router credential and therefore cannot self-promote by adding `DEPLOY`, lowering its cost class, or changing `RESERVE` back to `NORMAL`.

Eligibility can be checked repeatedly with `execution_eligibility`. A protected action should use a fresh decision; eligibility established at task start is not inherited forever.

## Capability downgrade

When a required capability disappears, the correct behavior is:

```text
completed work
    ↓
checkpoint
    ↓
CURRENT_RUNTIME_CAPABILITY_MISSING
    ↓
CHECKPOINT_AND_HANDOFF_MISSING_CAPABILITY_ONLY
```

The worker does not rediscover project state and does not redo completed implementation. MangoMe also does not silently pick a replacement model.

For example, if an implementation is complete but the current runtime no longer has `DEPLOY`, the remaining delta is deployment. The next routing decision must target that missing capability only.

## Cost governance and fan-out

The caller declares a `cost_ceiling` for each bounded delegation. A worker above the ceiling is ineligible. Difficulty, urgency, perceived importance, or the fact that MangoMe itself is being repaired do not raise that ceiling.

Additionally:

- `EXPENSIVE` and `PREMIUM` runtime profiles require explicit Owner approval bound to that exact `family + worker + task_key` delegation;
- multiple separately authorized high-cost delegations may coexist; per-worker `max_parallel_tasks` and host/orchestrator budgets govern concurrency;
- cheap/mechanical reconstruction may still use bounded parallel workers subject to each runtime's configured `max_parallel_tasks`;
- a cheap worker becoming ineligible does not authorize automatic escalation to a high-cost worker.

This is deliberately not provider-specific. A high-cost model can be Claude, GPT, Gemini, a local model, or another future runtime. One approval cannot be reused as a blanket license for additional premium tasks.

## Persisted delegation checkpoint

An authorized delegation records:

```text
task_key
coordinator_actor_id
worker_key
runtime_profile_id
purpose
required_capabilities
cost_ceiling
cost_class
input_scope
status
artifact
missing_delta
next_dependency
```

`complete_delegation` persists the result/checkpoint. `recovery_context` includes recent delegation state so coordinator/session death does not require reconstructing orchestration from logs, worktrees, or agent prose.

## MangoMe is not the model dispatcher

The inspected MangoMe repository does not contain the provider/model spawn implementation. That boundary matters.

`execution_eligibility` and `authorize_delegation` are deterministic policy and coordination decisions. They do **not** by themselves stop an external coordinator from calling a provider API directly.

Therefore the integration contract is normative:

> The external orchestrator MUST call MangoMe immediately before actual model dispatch and MUST refuse dispatch when `authorized != true`.

The same principle applies to capability-sensitive actions such as deployment: the host should re-check current eligibility before executing the action.

Until an actual orchestrator/provider dispatch path consumes this contract, MangoMe must report routing enforcement as an integration requirement rather than claiming that dispatch is technically blocked end-to-end.

## Recovery coordinator policy

For admitted work a recovery coordinator should perform:

```text
recovery_context
    ↓
classify missing delta
    ↓
required capabilities + cost ceiling
    ↓
execution_eligibility
    ↓
authorize_delegation
    ↓
external dispatch (only if authorized)
    ↓
complete_delegation
```

It must not replace either canonical state or routing decisions with its own repository archaeology or model-selection intuition.
