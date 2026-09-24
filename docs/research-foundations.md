# Research and reuse foundations

MangoMe is deliberately integration-first. The v0.1 architecture borrows established patterns instead of rebuilding them:

- MongoDB document storage and schema-versioning patterns for evolving state documents.
- MongoDB graph-style relationships and aggregation for typed work relations.
- Model Context Protocol for a provider-neutral agent interface.
- OpenSpec-style delta/spec evolution as inspiration for append-only contract contributions and effective specifications.
- Beads/Gas Town patterns for dependency-aware work, agent claiming and persistent task structure.
- W3C PROV concepts for future provenance alignment between entity, activity and agent.
- OpenTelemetry GenAI conventions for future model/token/runtime telemetry interoperability.
- CogC for capacity-aware execution-context compilation downstream of MangoMe state.

MangoMe's distinct role is the shared identity and operational-state layer that ties these concepts together across heterogeneous projects, physical file locations and model providers.
