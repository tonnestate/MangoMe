# UAI/1 compact semantic transport

MangoMe v0.1.3 introduces `UAI/1`, a versioned MangoMe profile for compact transport of execution semantics to agents.

## Non-goal

UAI/1 is not canonical storage and is not a general natural-language compression format. MongoDB/MangoMe remains the source of truth.

## Pipeline

```text
MangoMe canonical state
  -> ContextCompiler
  -> semantic execution projection
  -> UAI/1 encode + SHA-256 semantic hash
  -> worker
  -> UAI/1R structured result
  -> validate/decode/render
  -> normal MangoMe mutation/assurance tools
```

## Context packet

The packet uses short stable keys and tuple positions to reduce repeated schema tokens. The hash is calculated over the expanded semantic projection, not the compact wire representation.

Required envelope fields:

- `v`: `UAI/1`
- `p`: `mangome-work`
- `h`: SHA-256 of the canonical semantic projection
- `f`: family tuple
- `s`: current state tuple
- `ef`: effective-family tuple
- `sp`: specification tuple or null
- `w`: current work/slice tuple or null
- `c`: relevant contracts
- `e`: relevant evidence
- `r`: compact invariant rules

`expand_uai_context` reconstructs the projection and rejects hash mismatches.

## Result packet

Workers may answer with `UAI/1R`:

```json
{"v":"UAI/1R","h":"<context hash>","st":"SUCCESS","a":[["P",2,3],["D","done"]]}
```

Statuses: `SUCCESS`, `PARTIAL`, `BLOCKED`, `FAILED`.

Action codes:

- `P`: progress `["P", current_step, total_steps, optional_blocker]`
- `A`: artifact `["A", logical_name, artifact_type, storage_system, physical_location, optional_checksum]`
- `E`: evidence `["E", evidence_type, evidence_class, source, result, optional_artifact_id]`
- `D`: DONE claim `["D", optional_summary]`
- `N`: discovered slice `["N", declared_id, title, optional_objective]`
- `B`: blocker `["B", blocker]`

Decoded actions are proposals only. The decoder never calls `claim_done`, `submit_evidence`, `attach_artifact`, or any other mutation automatically.

## Rendering

`render_uai_result` provides deterministic English and German rendering. It translates protocol semantics and labels; free text supplied by a worker is preserved rather than machine-translated.

## Cost telemetry

Immediate compile metrics report characters plus a clearly labelled chars/4 heuristic. Production economics should use provider-reported token counts stored in `ExecutionReceipt`:

- `context_tokens_raw`
- `context_tokens_compiled`
- `context_tokens_interlingua`
- `output_tokens_interlingua`
- `interlingua_version`

The relevant measure is cost per verified outcome, not raw token reduction alone.
