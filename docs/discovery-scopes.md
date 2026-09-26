# Discovery scopes and physical asset identity

MangoMe separates logical work identity from physical locations. Repositories, worktrees, contracts, evidence and artifacts may be distributed across users, hosts, mount points and operating systems.

Typed discovery scopes are portable observations, not truth:

- `WORKSPACE`
- `CONTRACT_SOURCE`
- `ARTIFACT_SOURCE`
- `EVIDENCE_SOURCE`
- `REPOSITORY_SEARCH`
- `REFERENCE_ONLY`
- `AGENT_PRIVATE_CONTEXT`

Filesystem/Git locations are resolved by the host. No `/root`, `$HOME` layout or provider convention is part of the domain model. Repository-location discovery persists path, origin, HEAD, branches/worktrees and metadata as observations. It does not infer a Project/Family or promote a contract.

Generic file bodies remain in Git/filesystem/DMS/object storage. MangoMe stores bounded metadata, hashes, references, relations and explicitly admitted semantic state.
