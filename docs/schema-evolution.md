# Schema evolution

MangoMe schema version 2 adds revision control, explicit gate audit fields, plan binding, assurance-aware dependencies and evidence trust metadata.

Readers upgrade older documents in memory so old state remains readable. Persistence migration is explicit:

```bash
mangome migrate
mangome migrate --apply
```

The first command is a dry-run. The second persists registered migrations with revision-aware updates.

Unknown fields are preserved; migration does not destructively rewrite semantic content.
