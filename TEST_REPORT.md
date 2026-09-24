# Test Report — MangoMe v0.1.5

Date: 2026-09-24

Command:

```bash
PYTHONPATH=src python -m pytest -q
```

Result in the packaging environment:

```text
............................sss............                              [100%]
```

All runnable tests passed. Three integration/surface tests were skipped because their optional runtime dependency/environment was unavailable in the packaging sandbox.

New v0.1.5 coverage includes deterministic filesystem inventory, useful hidden work-directory scanning, secret/key exclusion, incremental unchanged-file behavior, removed-file detection, declared-ID reference lookup, live hash freshness, and rejection of audit/AI CLAIM material as reusable proof.
