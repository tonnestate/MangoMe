# MTB/2 — LOCAL_HOST MongoDB Trust Boundary

MangoMe v0.3.14 defines a deliberately simple managed single-host deployment profile.

```text
trusted Linux host
    |
    +-- MongoDB: loopback only, client access control not enforced
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
2. MongoDB client access control is not enforced (`authorization: disabled` or keyFile + `transitionToAuth: true`);
3. local processes on the host are within the deployment trust boundary.

MangoMe fails closed when a remote endpoint, MangoMe credential file, authenticated URI, or authenticated MangoMe MongoDB identity is detected. A preserved `security.keyFile` is allowed only through the bounded LOCAL_HOST transition path with `security.transitionToAuth: true`; the keyFile is internal MongoDB member-authentication material, not a MangoMe client credential.

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

## v0.3.16 zero-touch transition

On the supported managed Linux host, `LOCAL_HOST` readiness no longer requires an operator checklist when an older standalone `mongod.service` still has authorization enabled.

Before changing MongoDB authorization MangoMe must prove the live TCP listener is loopback-only. A managed root runtime may then back up the active `mongod.conf`, change only `security.authorization` to `disabled`, restart `mongod.service` once, and prove loopback-only scope again. Non-loopback listeners, command-line `--auth`, clustered/key-file/transition security, ambiguous configuration, or non-root execution fail closed before authorization is weakened.

Credential-era MangoMe files and process bindings are deleted only after the replacement credential-free loopback path is proven ready. MangoMe does not alter firewall/network configuration, `dbPath`, unrelated MongoDB settings, other databases, or MongoDB users/roles during this host transition.

Legacy database names are not deployment identity in v0.3.16. `mangome_uai_eval` is rejected for runtime use because schema drift cannot be assumed safe; it is never adopted, repaired, or migrated automatically.


## v0.3.17 keyFile-preserving transition

If the active loopback-only `mongod.service` contains `security.keyFile`, MangoMe no longer treats that fact alone as a terminal blocker. Zero-touch keeps the keyFile and any replication/member-authentication configuration unchanged and enables `security.transitionToAuth: true`. In that MongoDB transition state, user access control is not enforced, so MangoMe can use the same credential-free loopback client model while the keyFile remains available for internal member authentication.

The transition is allowed only after live listener scope is proven as LOOPBACK. MangoMe does not remove the keyFile or rewrite replica-set topology. Command-line cluster security and cluster-only/X.509 configurations without a keyFile remain fail-closed.
