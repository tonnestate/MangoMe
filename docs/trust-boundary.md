# MTB/1 — MongoDB Trust Boundary

MangoMe can enforce its invariants only when untrusted workers cannot bypass the service and write directly to the canonical MongoDB database.

v0.3.6 therefore adds an explicit MongoDB trust-boundary profile. The default `WARN` mode preserves compatibility and reports unsafe deployment characteristics. `STRICT` mode fails closed.

A strict production deployment requires:

```text
Worker / Agent process
    X  no canonical MongoDB credential

MangoMe service identity
    |  credential loaded from owner-only file
    |  expected OS uid verified
    v
MongoDB
    database-scoped runtime role
```

Configure strict mode with environment variables held by the MangoMe service, not the worker:

```text
MANGOME_TRUST_BOUNDARY=STRICT
MANGOME_MONGODB_URI_FILE=/etc/mangome/mongodb-uri
MANGOME_EXPECTED_SERVICE_UID=<uid-of-dedicated-mangome-user>
MANGOME_ENFORCE_LEAST_PRIVILEGE=1
```

The credential file must be a regular file owned by the MangoMe service uid with no group/other permission bits. In strict mode a MongoDB URI supplied directly through `MANGOME_MONGODB_URI` is rejected because child/worker processes can inherit environment variables.

Remote MongoDB endpoints are rejected in strict mode unless the deployment explicitly sets `MANGOME_ALLOW_REMOTE_MONGODB=1` and provides the network/authentication controls required for that environment. Loopback or a local socket is the default trust posture.

When `MANGOME_ENFORCE_LEAST_PRIVILEGE=1`, MangoMe inspects authenticated built-in MongoDB roles where the server permits it and rejects known global/admin roles such as `root`, `dbOwner`, `readWriteAnyDatabase`, `userAdminAnyDatabase`, and `clusterAdmin`. Custom deployment-specific roles remain possible.

`trust_boundary_status` and `health` expose only sanitized posture metadata. They never return the MongoDB URI, username, password, credential-file contents, or other secrets.

MTB/1 cannot magically revoke credentials already given to an untrusted worker. The strict profile makes the required deployment boundary explicit and fail-closed; the host must run MangoMe under a separate OS/service identity and keep the credential file inaccessible to workers.
