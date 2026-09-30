# MTB/2 — LOCAL_HOST MongoDB Trust Boundary

MangoMe v0.3.14 defines a deliberately simple managed single-host deployment profile.

```text
trusted Linux host
    |
    +-- MongoDB: loopback only, authorization disabled
    |
    +-- MangoMe: no MongoDB principal / password / role
```

The default managed profile is:

```text
MANGOME_TRUST_BOUNDARY=LOCAL_HOST
MANGOME_DATABASE=mangome
mongodb://127.0.0.1:27017
```

## Preconditions

LOCAL_HOST is valid only when:

1. MongoDB listens only on loopback (`127.0.0.1`, `localhost`, or `::1`);
2. MongoDB authorization is disabled;
3. local processes on the host are within the deployment trust boundary.

MangoMe fails closed when a remote endpoint, credential file, authenticated URI,
authenticated MongoDB identity, or enabled MongoDB authorization is detected.

## No credential lifecycle

LOCAL_HOST deliberately has no:

- `mangome_runtime` MongoDB user;
- maintenance/admin MangoMe MongoDB user;
- MongoDB credential file;
- credential discovery/adoption;
- role bootstrap;
- temporary no-auth MongoDB process.

Stale v0.3.12/v0.3.13 credential files/configuration must be removed during migration.

## Legacy databases

A legacy database is not proof of compatible state. MangoMe does not infer that an
older database can be repaired into the current schema.

`mangome_uai_eval` is therefore rejected for runtime selection with
`LEGACY_DATABASE_SCHEMA_DRIFT`. It may only be removed by the explicitly confirmed
exact-allowlist total reset.

## Security consequence

With MongoDB authorization disabled, any local process that can reach the loopback
MongoDB listener can access MongoDB. LOCAL_HOST is therefore unsuitable for an
untrusted multi-user machine. The security boundary is the host, not MongoDB RBAC.
