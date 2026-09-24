# External model reconciliation — next stage

MangoMe should support external reviews without making an external model a source of truth.

Proposed flow:

```text
MangoMe canonical state
  ↓
compile comparison package
  ↓
external reviewer (Claude / ChatGPT API / Gemini / other MCP-capable client)
  ↓
review result + provenance
  ↓
SUGGESTED edge / evidence / conflict report
  ↓
normal MangoMe approval or verification path
```

For ChatGPT consumer Plus accounts, direct unattended cross-session/API invocation cannot be assumed. An API or connector-capable environment would be a separate integration. Claude and other MCP hosts can consume the MangoMe MCP directly when configured.

The adapter should therefore be capability-based, not provider-name-based.
