# Big-Bang import

The Big-Bang scanner is deliberately non-destructive.

It walks configured roots, hashes readable text artifacts, extracts cheap structural signals, classifies the artifact and registers its physical location. It never moves, renames, merges or deletes source files.

A discovered `CONTRACT_CANDIDATE` is not automatically a canonical contract. Canonical onboarding happens explicitly with `import_contract_bundle` or normal contract registration. This separates inventory from semantic truth.

The preferred escalation order for future reconciliation is: structured fields → known parsers → deterministic rules → lexical/regex extraction → graph context → cheap classifier → strong model → human approval.
