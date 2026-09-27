# MangoMe design decisions

## Rich canonical model is intentional

MangoMe optimizes for durable operational truth across long-lived multi-agent work. Projects, contract families, contributions, specs, plans, slices, evidence, artifacts, graph edges, approvals and execution receipts remain distinct because they have distinct identity, provenance and lifecycle semantics.

Interface complexity should be reduced through composition (`begin_work`), context compilation and upstream routing, not by deleting canonical semantics.

## MongoDB is the canonical production store

MangoMe is simultaneously a document store, work graph and state machine. Evolving heterogeneous documents, nested gates/evidence and append-only contributions are core workload characteristics.

The in-memory backend is a test/dev implementation. v0.1.x does not target interchangeable production persistence backends.

## Bureaucracy is controlled at the surface

`begin_work` composes the existing request -> plan -> start lifecycle for bounded work. It does not bypass a current effective spec, persisted plan or slice binding.

IntakeGov is the preferred future decision point for proportional governance depth. MangoMe remains the truth system.

## Compact transport does not replace truth

UAI/1 packets are disposable semantic projections. They are hash-bound, round-trippable within their defined projection, and may be regenerated at any time from MangoMe.

## No federation in current scope

MangoMe v0.1.x assumes one canonical deployment and one canonical MongoDB truth serving many projects, agents, models and humans. Cross-organization federation, portable trust domains, key exchange and server-independent shared truth are deliberately outside the current product scope.


## v0.3 — WorkIdentity outranks Playbook and Spec lifecycle

Decision: MangoMe's durable anchor is WorkIdentity, not a file path, Playbook, Contract body, Specification file, Plan, Slice, or agent session. Specifications may evolve and Playbooks may be replaced without changing WorkIdentity. Assurance history is Work-bound and baseline-attributed. Progressive state is crash-recovery state only and cannot self-promote into canonical truth.

Rationale: earlier Contract-first recovery over-coupled identity to normative artifacts, while a naive Playbook-first design would let procedural instructions become an authority substitute. The v0.3 control plane separates identity, normative truth, procedure, execution and assurance.
