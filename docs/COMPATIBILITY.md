# Compatibility

MangoMe separates what is **covered by the release suite**, what is **supported by managed configuration**, and what remains **deployment-dependent**.

## Release-suite coverage

The repository test/release suite covers:

- Python 3.10, 3.11 and 3.12;
- MongoDB 7 integration;
- MCP v2 tool-surface discovery using the installed `mcp` dependency;
- the complete deterministic test suite and source compilation;
- wheel construction and inclusion of `mangome/skill/SKILL.md`.

## Managed client integration

MangoMe contains managed setup/attestation logic for:

- Codex;
- Claude Code.

Client releases can change independently of MangoMe. Managed setup and `mangome attest-client` prove the configuration MangoMe can observe; they do not claim control over undocumented client internals.

## Deployment-dependent

The following cannot be proven by the repository test suite alone:

- a specific host's Codex/Claude session actually consuming the current Skill;
- production MongoDB credentials, OS/service identity, network policy and strict trust-boundary deployment;
- an external orchestrator actually enforcing MangoMe delegation decisions at its provider dispatch boundary;
- external API/filesystem/deployment effects satisfying provider-specific idempotency and reconciliation semantics.

These require host/runtime acceptance tests.

## Release rule

Do not turn a supported configuration path into a universal compatibility claim. State separately what was tested, what is configured, and what is enforced end-to-end.
