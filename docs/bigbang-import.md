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
