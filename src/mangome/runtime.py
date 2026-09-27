from __future__ import annotations

import os

from .work_control import WorkGovernedMangoMeService
from .service import MangoMeService, workspace_project_key
from .storage.memory import InMemoryStore
from .storage.mongo import MongoStore
from .operability import OperabilityError, attach_workspace, enforce_expected_identity, resolve_workspace_root

_service: MangoMeService | None = None
_workspace_attachment: dict[str, object] | None = None
_session_restore: dict[str, object] | None = None


def bind_workspace_read_only(workspace_root: str | None = None) -> dict[str, object]:
    """Bind the process to a workspace path without discovery, scanning, or persistence.

    This is the zero-touch fast path used during MCP/runtime startup and recovery.
    It deliberately does not call ``attach_workspace`` because attachment may perform
    candidate inventory/Big-Bang discovery for an unadmitted workspace. Discovery is
    an explicit maintenance/onboarding concern and must never block cognition.
    """
    root = resolve_workspace_root(workspace_root)
    return {
        "workspace_root": str(root),
        "binding_mode": "READ_ONLY_FAST_PATH",
        "discovery_deferred": True,
        "canonical_mutations": 0,
        "rule": "BINDING_IS_NOT_DISCOVERY; productive effects reconcile canonical state lazily.",
    }


def ensure_workspace_binding(workspace_root: str | None = None) -> dict[str, object]:
    """Return a volatile read-only workspace binding, creating only that binding if absent."""
    global _workspace_attachment
    if _workspace_attachment is not None:
        if workspace_root is None:
            return _workspace_attachment
        try:
            from pathlib import Path
            current = _workspace_attachment.get("workspace_root")
            requested = resolve_workspace_root(workspace_root)
            if current and Path(str(current)).resolve() == requested:
                return _workspace_attachment
        except OSError:
            pass
    _workspace_attachment = bind_workspace_read_only(workspace_root)
    return _workspace_attachment


def get_service() -> MangoMeService:
    global _service, _workspace_attachment, _session_restore
    if _service is not None:
        return _service
    enforce_expected_identity()
    backend = os.environ.get("MANGOME_BACKEND", "mongo").lower()
    database = os.environ.get("MANGOME_DATABASE", "mangome")
    expected_database = os.environ.get("MANGOME_EXPECTED_DATABASE", "").strip()
    if backend != "memory" and expected_database and database != expected_database:
        raise OperabilityError(
            "WRONG_MANGOME_DATABASE",
            f"managed MangoMe binding expects database {expected_database!r}, running configuration selects {database!r}",
        )
    if backend == "memory":
        store = InMemoryStore()
    else:
        uri = os.environ.get("MANGOME_MONGODB_URI", "mongodb://127.0.0.1:27017")
        store = MongoStore(uri, database)
    _service = WorkGovernedMangoMeService(store)
    if os.environ.get("MANGOME_AUTO_ATTACH", "").strip().lower() in {"1", "true", "yes", "on"}:
        # v0.3.4 hotfix: startup binding must be cheap and non-blocking.  Do not
        # inventory the filesystem and do not run canonical recovery merely because
        # the MCP process started.  Reconciliation is lazy at the effect boundary.
        _workspace_attachment = bind_workspace_read_only(os.environ.get("MANGOME_WORKSPACE_ROOT"))
    return _service



def set_session_restore_snapshot(value: dict[str, object] | None) -> None:
    global _session_restore
    _session_restore = value


def session_restore_snapshot() -> dict[str, object] | None:
    return _session_restore

def workspace_attachment_snapshot() -> dict[str, object] | None:
    return _workspace_attachment


def restore_workspace_state(workspace_root: str | None = None) -> dict[str, object]:
    """Read canonical recovery state using only the volatile workspace binding.

    This function never performs filesystem inventory, Big-Bang discovery, or
    repository scanning.  It is the bounded recovery primitive used by MCP restore,
    assignment reconciliation, and effect gates.
    """
    current = workspace_attachment_snapshot() or ensure_workspace_binding(workspace_root)
    root = str((current or {}).get("workspace_root") or workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    project_key = workspace_project_key(root)
    result = get_service().session_restore(project_key)
    set_session_restore_snapshot(result)
    return result


def refresh_workspace_attachment(workspace_root: str | None = None, *, force: bool = False) -> dict[str, object]:
    global _workspace_attachment
    # get_service() may perform the first automatic attachment. Reuse that result
    # instead of immediately attaching a second time and misreporting first_attach=False.
    service = get_service()
    if _workspace_attachment is not None and not force:
        # A volatile READ_ONLY_FAST_PATH binding is intentionally not a completed
        # attachment. An explicit refresh request must promote it to the full
        # candidate-only attachment/discovery path.
        if _workspace_attachment.get("binding_mode") != "READ_ONLY_FAST_PATH":
            requested = workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT")
            if requested is None:
                return _workspace_attachment
            try:
                from pathlib import Path
                current = _workspace_attachment.get("workspace_root")
                if current and Path(str(current)).resolve() == Path(requested).expanduser().resolve():
                    return _workspace_attachment
            except OSError:
                pass
    _workspace_attachment = attach_workspace(service, workspace_root)
    return _workspace_attachment


def health_snapshot() -> dict[str, object]:
    """Return a health report even when backing-store bootstrap fails.

    Health is an observability boundary, so it must not require a successfully
    constructed MangoMeService. Diagnostics intentionally expose only the
    exception class and a sanitized category, never connection strings or
    exception messages that may contain credentials.
    """
    from . import __version__
    from .schema import CURRENT_SCHEMA_VERSION

    backend = os.environ.get("MANGOME_BACKEND", "mongo").lower()
    database = os.environ.get("MANGOME_DATABASE", "mangome") if backend != "memory" else None
    backend_name = "memory" if backend == "memory" else "mongodb"

    try:
        service = get_service()
        store_health = service.store.health()
    except Exception as exc:  # health must survive failed store/bootstrap initialization
        error_type = type(exc).__name__
        code = getattr(exc, "code", None)
        if isinstance(exc, OperabilityError):
            diagnostic = "MangoMe client/runtime identity or workspace attachment failed"
        elif code == 13 or error_type in {"AuthenticationFailure", "OperationFailure"}:
            diagnostic = "MongoDB authorization failed during MangoMe initialization"
        elif error_type in {"ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect"}:
            diagnostic = "MongoDB is unreachable"
        else:
            diagnostic = "MangoMe backing-store initialization failed"
        store: dict[str, object] = {
            "ok": False,
            "backend": backend_name,
            "error_type": error_type,
            "diagnostic": diagnostic,
        }
        if isinstance(exc, OperabilityError):
            store["reason_code"] = exc.code
        if database is not None:
            store["database"] = database
        return {
            "ok": False,
            "version": __version__,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "store": store,
        }

    return {
        "ok": bool(store_health.get("ok")),
        "version": __version__,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "store": store_health,
        "workspace_attachment": _workspace_attachment,
    }


def reset_service_for_tests() -> None:
    """Reset process-global service/bootstrap state. Intended for tests only."""
    global _service, _workspace_attachment, _session_restore
    _service = None
    _workspace_attachment = None
    _session_restore = None
