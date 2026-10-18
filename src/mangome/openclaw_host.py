"""OpenClaw host adapter — agent-runtime integration owned by MangoMe (FS-OPENCLAW-BOUNDARY-016).

Ownership: MangoMe owns the host-side adapter, its lifecycle (register, connect, disconnect), session binding and execution authorization towards an OpenClaw runtime.
PeachMe owns only the provider-independent admission interface (`SessionStore.assert_execution_authority`); PlumMe owns model supply. OpenClaw as a *runtime* is not a model
provider: nothing in this module routes inference.

Truthful capability reporting: `capability_report()` states, per capability, PROVEN / ABSENT / UNKNOWN with the evidence behind it. A stopped runtime (installed, not running) is
reported as exactly that, never as a missing adapter; a declared hook list or an installed adapter is never a connected, executable runtime.

This module imports nothing from PeachMe: the session store is injected (any object with ``assert_execution_authority(session_id, revision)``), so there is no import cycle.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

REQUIRED_INTERCEPTIONS = frozenset({"pre_model", "pre_tool", "tool_result", "terminal_receipt"})

# Capability vocabulary (ordered chain; UNAVAILABLE/UNKNOWN are statuses of the chain, not links).
CODE_PRESENT = "CODE_PRESENT"
ADAPTER_REGISTERED = "ADAPTER_REGISTERED"
RUNTIME_INSTALLED = "RUNTIME_INSTALLED"
RUNTIME_RUNNING = "RUNTIME_RUNNING"
CONNECTED = "CONNECTED"
EXECUTABLE = "EXECUTABLE"
UNAVAILABLE = "UNAVAILABLE"
UNKNOWN = "UNKNOWN"
CHAIN = (CODE_PRESENT, ADAPTER_REGISTERED, RUNTIME_INSTALLED, RUNTIME_RUNNING, CONNECTED, EXECUTABLE)
PROVEN, ABSENT = "PROVEN", "ABSENT"


class OpenClawHostError(RuntimeError):
    """Fail-closed refusal with a stable machine-readable code (message == code)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AuthorityStore(Protocol):
    def assert_execution_authority(self, session_id: str, revision: int) -> None: ...


@dataclass(frozen=True)
class CapabilityReport:
    declared: tuple[str, ...]
    missing: tuple[str, ...]
    enforced: bool


@dataclass
class Evidence:
    """What has actually been observed about the runtime; each field is set only by an observation, never by configuration alone."""
    connection: dict | None = None          # {"session_id", "attested_capabilities", "attested_by"} from a host handshake
    executions: list[dict] = field(default_factory=list)      # terminal receipts of executions authorized through this adapter


_REGISTRY: dict[str, "OpenClawHostAdapter"] = {}


class OpenClawHostAdapter:
    """Decision-side tool gate for the trusted host. The caller must be the trusted host: this gate cannot stop a caller from avoiding it, and a live runtime adapter must still
    prove that all tool/model paths are covered (`connect` records that attestation)."""

    name = "openclaw"

    def __init__(self, *, capabilities: set[str], approve_effect: Callable[[str, str], bool], store: AuthorityStore | None = None):
        if not callable(approve_effect):
            raise OpenClawHostError("HOST_EFFECT_AUTHORITY_REQUIRED")
        self.capabilities = frozenset(capabilities)
        self.approve_effect = approve_effect
        self.store = store
        self.evidence = Evidence()
        self.state = "STOPPED"                  # STOPPED -> CONNECTED -> STOPPED; the adapter never starts or stops the OpenClaw process itself

    # ---------------------------------------------------------------- registry / lifecycle
    def register(self) -> "OpenClawHostAdapter":
        _REGISTRY[self.name] = self
        return self

    def unregister(self) -> None:
        if _REGISTRY.get(self.name) is self:
            del _REGISTRY[self.name]

    def connect(self, *, session_id: str, attested_capabilities: set[str], attested_by: str) -> None:
        """Record a runtime handshake: the host (not this process) attests which interceptions the live runtime actually enforces. Declared hook names alone never connect."""
        if not (session_id and attested_by):
            raise OpenClawHostError("OPENCLAW_HANDSHAKE_EVIDENCE_REQUIRED")
        if not REQUIRED_INTERCEPTIONS <= set(attested_capabilities):
            raise OpenClawHostError("OPENCLAW_RUNTIME_INTERCEPTION_INCOMPLETE")
        self.evidence.connection = {"session_id": session_id, "attested_capabilities": sorted(attested_capabilities), "attested_by": attested_by}
        self.state = "CONNECTED"

    def disconnect(self) -> None:
        self.evidence.connection = None
        self.state = "STOPPED"

    def record_execution(self, *, session_id: str, receipt_id: str) -> None:
        """A terminal receipt for an execution that this adapter authorized: the only evidence that EXECUTABLE rests on."""
        if self.state != "CONNECTED" or not receipt_id:
            raise OpenClawHostError("OPENCLAW_NOT_CONNECTED")
        self.evidence.executions.append({"session_id": session_id, "receipt_id": receipt_id})

    # ---------------------------------------------------------------- interception contract
    def report(self) -> CapabilityReport:
        missing = tuple(sorted(REQUIRED_INTERCEPTIONS - self.capabilities))
        return CapabilityReport(tuple(sorted(self.capabilities)), missing, not missing)       # local decision coverage, not a live runtime certificate

    def require_full_enforcement(self) -> None:
        if not self.report().enforced:
            raise OpenClawHostError("OPENCLAW_RUNTIME_INTERCEPTION_INCOMPLETE")

    def _assert_authority(self, session_id: str, revision: int) -> None:
        if self.store is None:
            raise OpenClawHostError("OPENCLAW_SESSION_STORE_REQUIRED")
        try:
            self.store.assert_execution_authority(session_id, revision)                  # PeachMe's provider-independent admission snapshot
        except Exception as exc:                                                         # PeachError and friends carry their code as message
            code = str(exc)
            raise OpenClawHostError("OPENCLAW_SESSION_NOT_READY" if code == "SESSION_NOT_READY" else code) from exc

    def authorize_tool(self, session_id: str, tool_name: str, *, expected_revision: int | None = None) -> None:
        self.require_full_enforcement()
        if not isinstance(session_id, str) or not session_id or not isinstance(tool_name, str) or not tool_name:
            raise OpenClawHostError("INVALID_TOOL_AUTHORITY_REQUEST")
        if expected_revision is None:
            raise OpenClawHostError("OPENCLAW_REVISION_REQUIRED")
        self._assert_authority(session_id, expected_revision)
        if self.approve_effect(session_id, tool_name) is not True:
            raise OpenClawHostError("TOOL_EFFECT_DENIED")
        self._assert_authority(session_id, expected_revision)            # host policy may be slow: never grant a decision that became stale meanwhile
        # A later state change is still possible: the host must bind the actual dispatch to this admitted revision or recheck immediately.


# -------------------------------------------------------------------- truthful capability report
def _running_processes(name: str) -> tuple[bool | None, list[int]]:
    """(found?, pids) from /proc. None when /proc cannot be read (then 'running' is UNKNOWN, not absent)."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None, []
    pids = []
    for p in proc.iterdir():
        if not p.name.isdigit():
            continue
        try:
            comm = (p / "comm").read_text().strip().lower()
            first = os.path.basename((p / "cmdline").read_bytes().split(b"\0", 1)[0].decode(errors="ignore")).lower()
        except OSError:
            continue
        if name in (comm, first):                      # exact executable name, not a substring of some path or argument
            pids.append(int(p.name))
    return True, pids


def capability_report(adapter: "OpenClawHostAdapter | None" = None, *, binary: str = "openclaw", install_paths: tuple[str, ...] = ()) -> dict:
    """Per capability PROVEN / ABSENT / UNKNOWN with evidence. `summary` is the highest link whose predecessors are all PROVEN; `stopped_runtime` is true exactly when an installed runtime is
    observed not running. Nothing is inferred upward: a catalogue, a fixture or a declared hook list proves none of the later links."""
    adapter = adapter or _REGISTRY.get("openclaw")
    rows: dict[str, dict] = {c: {"status": UNKNOWN, "evidence": []} for c in CHAIN}
    rows[CODE_PRESENT] = {"status": PROVEN, "evidence": [f"module {__name__} imported; OpenClawHostAdapter available"]}
    registered = _REGISTRY.get("openclaw") is not None
    rows[ADAPTER_REGISTERED] = {"status": PROVEN if registered else ABSENT, "evidence": ["adapter instance registered in this process"] if registered else ["no adapter registered in this process"]}
    found = shutil.which(binary) or next((p for p in install_paths if os.path.exists(p)), None)
    rows[RUNTIME_INSTALLED] = {"status": PROVEN, "evidence": [f"executable at {found}"]} if found else {"status": ABSENT, "evidence": [f"`{binary}` not found on PATH or in the given install paths"]}
    seen, pids = _running_processes(binary)
    if seen is None:
        rows[RUNTIME_RUNNING] = {"status": UNKNOWN, "evidence": ["process table not readable"]}
    elif pids:
        rows[RUNTIME_RUNNING] = {"status": PROVEN, "evidence": [f"process {binary} pid(s) {pids[:5]}"]}
    else:
        rows[RUNTIME_RUNNING] = {"status": ABSENT, "evidence": [f"no running `{binary}` process"]}
    conn = adapter.evidence.connection if adapter else None
    rows[CONNECTED] = ({"status": PROVEN, "evidence": [f"handshake attested by {conn['attested_by']} for session {conn['session_id']}"]} if conn
                       else {"status": ABSENT if adapter else UNKNOWN, "evidence": ["no host handshake recorded" if adapter else "no adapter to ask"]})
    execs = adapter.evidence.executions if adapter else []
    rows[EXECUTABLE] = ({"status": PROVEN, "evidence": [f"{len(execs)} authorized execution receipt(s)"]} if conn and execs
                        else {"status": UNKNOWN, "evidence": ["connected but no authorized execution observed yet" if conn else "requires CONNECTED and an authorized execution receipt"]})
    summary = None
    for c in CHAIN:
        if rows[c]["status"] != PROVEN:
            break
        summary = c
    stopped = rows[RUNTIME_INSTALLED]["status"] == PROVEN and rows[RUNTIME_RUNNING]["status"] == ABSENT
    return {"summary": summary or UNAVAILABLE, "capabilities": rows, "stopped_runtime": stopped,
            "adapter_missing": rows[ADAPTER_REGISTERED]["status"] == ABSENT,
            "note": "OpenClaw is a runtime, not a model provider; model supply is reported by PlumMe."}
