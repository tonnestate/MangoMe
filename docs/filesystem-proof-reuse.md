# Filesystem inventory, RB/1 and Evidence freshness

MangoMe 0.1.5 added deterministic filesystem inventory. MangoMe 0.1.6 adds **RB/1**, a structured reproduction binding stored inside the existing `Evidence.payload`. RB/1 is not a new Proof entity or a second assurance lifecycle.

The core rule remains:

> Reuse current, reproducibly bound Evidence — not previous AI conclusions.

## 1. Filesystem inventory

`filesystem_scan` walks explicitly supplied roots and persists observable filesystem facts:

- absolute and relative path;
- role (`SOURCE`, `TEST`, `CONTRACT`, `AUDIT_OR_REPORT`, `WORKFLOW`, `CONFIG`, `DOCUMENTATION`, `OTHER`);
- SHA-256 when the file is within the configured hash bound;
- size and nanosecond mtime;
- lexically detected declared contract/work IDs;
- nearest discovered Git repository root and HEAD;
- whether the file is currently present.

Sensitive/key files and common secret/cache/build directories are excluded. Useful hidden work directories such as `.github`, `.gitlab`, and `.devcontainer` are not discarded merely because they are hidden.

The scanner does not create Contracts, Slices, Verification, Acceptance, or implementation truth.

Repeated scans reuse persisted inventory state and do not rewrite unchanged records. They still walk the configured roots. v0.1.6 is not a filesystem watcher or Git-delta scanner.

## 2. Reference lookup

`filesystem_references(declared_id)` finds indexed files that lexically mention a declared ID. This is navigation only. A filename, source comment, test name, or report that references a Contract is not proof of implementation.

```text
legacy contract id
    -> filesystem_references
    -> likely source/tests/config/workflows
    -> targeted current verification
```

## 3. RB/1 reproduction binding

`build_reproduction_binding` creates an `RB/1` structure from current observable facts. It **does not execute the command**. The caller supplies the command and exit code from a run performed outside this helper.

Required binding fields are:

```text
version = RB/1
command
cwd
exit_code
input_bindings[] = path + sha256 + role
fingerprint
```

Additional provenance may include:

```text
git_commit
output_artifact_id
stdout_sha256
stderr_sha256
environment_names[]
```

Environment values are never accepted by RB/1. The helper records names only and rejects names that look like passwords, tokens, secrets, API keys, private keys or credentials. If dependency/configuration state matters, bind the corresponding lockfile/configuration file as an input.

The deterministic fingerprint covers the semantic RB/1 fields but excludes volatile capture time and the fingerprint field itself. Input bindings and environment names are canonicalized before hashing so ordering does not change the fingerprint.

Typical usage:

```text
1. execute the test/check in the real runtime
2. retain its command + exit code + relevant outputs
3. build_reproduction_binding(...)
4. submit_evidence(payload={"reproduction": <RB/1>}, ...)
5. verifier/owner attests the Evidence
6. normal gate / verify_slice path
```

Attestation remains important: RB/1 makes a claim inspectable and freshness-checkable; it does not independently prove that the caller really executed the command it reports.

## 4. Evidence freshness

`evidence_freshness(evidence_id)` first requires the existing normal MangoMe conditions for reusable Evidence:

- admissible Evidence class;
- verifier/owner attestation;
- PASS verdict.

For RB/1 Evidence it then checks:

- binding version;
- reproduction fingerprint integrity;
- `exit_code == 0` for PASS Evidence;
- current hashes/presence of all declared input files;
- current Git HEAD when an expected commit exists;
- optional output Artifact presence and filesystem checksum where available.

Possible top-level states remain:

- `REUSABLE` — all declared live-checkable bindings remain current;
- `STALE` — a bound input/output changed or disappeared;
- `UNKNOWN` — exact current context cannot be established;
- `UNBOUND` — no usable hashed input binding exists;
- `INADMISSIBLE` — Evidence/binding does not satisfy reuse rules.

Reason codes provide more detail, including:

```text
SOURCE_CHANGED
SOURCE_MISSING
TEST_CHANGED
TEST_MISSING
INPUT_CHANGED
INPUT_MISSING
INPUT_UNCHECKABLE
OUTPUT_CHANGED
OUTPUT_MISSING
OUTPUT_UNREADABLE
COMMIT_CHANGED
GIT_UNAVAILABLE
FINGERPRINT_MISSING
FINGERPRINT_MISMATCH
EXIT_CODE_NONZERO
```

A Git commit mismatch is conservative `UNKNOWN` when declared input hashes still match. A different repository HEAD does not itself prove a relevant dependency changed, but MangoMe also cannot claim exact-context reproducibility without a complete dependency closure.

## 5. Legacy compatibility

v0.1.5 `payload.filesystem_bindings` continue to work. They remain weaker than RB/1 because they do not carry command, exit-code, Git-context or reproduction-fingerprint metadata.

Historical AI audit prose remains a `CLAIM`/report and is never promoted merely because it says “implemented”, “verified” or “all tests passed”.

## 6. What RB/1 deliberately does not do

RB/1 does not:

- run or sandbox tests;
- store environment-variable values or secrets;
- infer that the declared input set is complete;
- infer Requirement ↔ Evidence semantic coverage;
- infer cross-Slice proof equivalence;
- create `VERIFIED` or `ACCEPTED`;
- reconstruct missing historical Slices;
- make an old audit trustworthy.

If current assurance is required and Evidence is stale, unknown or insufficiently bound, create/run a **present-day revalidation Slice**. That proves the current implementation state; it does not fabricate historical provenance.
