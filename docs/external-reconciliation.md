# External model reconciliation — next-stage adapter

MangoMe can already store external reviews safely, but v0.1.2 does not invoke ChatGPT/Claude/Gemini providers itself.

Intended flow:

```text
MangoMe canonical state
  ↓
compile bounded comparison package
  ↓
external reviewer
  ↓
EXTERNAL_REVIEW evidence + suggested relations/conflicts
  ↓
UNATTESTED by default
  ↓
trusted verifier/owner attestation when appropriate
  ↓
normal gate / verification / approval path
```

An external model is never a direct writer of canonical semantic truth.

Consumer ChatGPT subscriptions should not be assumed to provide unattended API/session access. Provider invocation belongs in a capability-specific adapter or connected runtime. Claude or other MCP-capable hosts may consume MangoMe directly when configured.

The adapter should therefore be capability-based rather than provider-name-based.
