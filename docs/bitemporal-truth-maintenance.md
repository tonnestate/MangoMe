# BTTM/1 — Bitemporal Truth Maintenance

MangoMe v0.3.6 adds a canonical truth-maintenance layer without replacing MongoDB or turning model confidence into truth.

BTTM/1 keeps two independent time axes for each canonical assertion:

- `valid_from` / `valid_to`: when the assertion is claimed to hold in the represented world.
- `known_from` / `known_to`: when that assertion version was part of MangoMe's canonical knowledge.

This distinction allows MangoMe to answer both “what was true at time T?” and “what did the organization know at time T?” without rewriting history.

Assertions may be grounded by Evidence or by typed links to other assertions: `support_ids`, `assumption_ids`, `depends_on`, and `contradicts`. A bare worker statement with no grounding remains `UNSUPPORTED`.

Current support states are:

- `SUPPORTED`
- `UNSUPPORTED`
- `CONTRADICTED`
- `REVALIDATION_REQUIRED`

Invalidation is non-destructive. It closes the assertion's known-time interval, records a canonical truth event, and propagates `REVALIDATION_REQUIRED` through dependent current assertions. Historical queries can still reconstruct the earlier state.

BTTM and PCH are deliberately orthogonal:

```text
BTTM/1: what MAY currently be supported as true?
PCH/1:  what SHOULD currently be cognitively resident?
ContextCompiler: what CAN fit in this worker context?
```

A revalidation requirement raises attention in PCH, but never changes assurance or normative authority by itself.

Canonical truth mutation requires an existing WorkIdentity and a bound current work turn. Creating assertions requires `VERIFY` or `MODIFY`; invalidating canonical assertions requires `MODIFY`.
