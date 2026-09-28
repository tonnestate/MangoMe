# Big-Bang import and reconciliation

Big-Bang remains deliberately non-destructive.

`bigbang_scan` inventories configured filesystem roots, hashes supported text artifacts and extracts cheap structural signals. Identifier patterns are generic by default and may be supplied explicitly or through `MANGOME_ID_PATTERNS_JSON`.

When enabled, Git discovery also records repository origin, HEAD, local branches, worktrees and recent commit metadata. No checkout, reset, merge, rename or file mutation is performed.

Discovery classifications such as `CONTRACT_CANDIDATE` and `WORK_STRUCTURE_CANDIDATE` are not canonical truth.

`reconcile_bigbang` compares discovered declared IDs with existing canonical contracts and returns:

- exact matches;
- declared-ID collisions;
- unresolved artifacts;
- slice markers associated with the candidate.

It performs zero semantic mutations. Admission into a family/contract/slice graph remains explicit.

Preferred escalation order:

```text
structured fields
→ known parsers
→ deterministic rules
→ narrow lexical/regex extraction
→ graph context
→ cheap classifier
→ strong model
→ human/authorized decision
```


## v0.3.9 observation surfaces

`bigbang_scan` is the terminal fast path for an explicit discovery request. It is service-free, persists no Artifact rows, defaults Git inspection off, and returns a bounded record preview. A simple `discover PATH` request should call it exactly once and stop.

When the user explicitly asks to compare candidates with canonical state, use `reconcile_bigbang_scan`; it performs scan + advisory reconciliation server-side and avoids sending hundreds of candidate records back through model context. Direct `reconcile_bigbang(records)` is retained for small caller-supplied candidate sets and rejects oversized payloads.

`filesystem_inventory` is likewise ephemeral/read-only. `filesystem_scan` remains the explicit persistent inventory/onboarding surface. Pure observation is allowed even when admitted work exists; the prohibition is against using discovery to *reconstruct* admitted WorkIdentity or current state.

Big-Bang text discovery skips symlinks plus private agent/credential/cache/build trees and secret-like files. File SHA-256 is streamed while only a bounded prefix is decoded for structural classification.
Traversal itself is bounded by `max_files` and `max_depth`; excluded directories are pruned before descent rather than merely filtered after traversal. This prevents a small requested result preview from hiding an unbounded filesystem walk.

## Portable multi-root discovery

A workspace is not assumed to equal one filesystem root. Hosts may provide typed scopes through `MANGOME_DISCOVERY_SCOPES_JSON` (for example `CONTRACT_SOURCE`, `ARTIFACT_SOURCE`, `EVIDENCE_SOURCE`, `REPOSITORY_SEARCH`). Paths are resolved on the current host; MangoMe does not hard-code `/root`, a username or an operating-system layout.

Cheap Git-location discovery may inspect bounded search roots such as the workspace parent/home or `MANGOME_REPOSITORY_SEARCH_ROOTS_JSON`, but it records physical repository/worktree identity only. It never creates canonical project truth. Generic file bodies remain in their source system; MangoMe stores bounded metadata, hashes and references. Agent-private `.claude`/`.codex` context is not a project-truth source.
