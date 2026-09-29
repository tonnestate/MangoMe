from __future__ import annotations

import os
from pathlib import Path

from .work_control import WorkGovernedMangoMeService
from .service import MangoMeService, workspace_project_key
from .storage.memory import InMemoryStore
from .storage.mongo import MongoStore
from .trust_boundary import resolve_mongodb_connection, enforce_mongo_role_boundary
from .operability import OperabilityError, attach_workspace, enforce_expected_identity, resolve_workspace_root

_service: MangoMeService | None = None
_workspace_attachment: dict[str, object] | None = None
_session_restore: dict[str, object] | None = None
_database_bootstrap_attempted = False
_database_bootstrap_snapshot: dict[str, object] | None = None
_database_bootstrap_error: tuple[str, str] | None = None

_LEGACY_EVAL_DATABASES = {"mangome_uai_eval"}

def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}

def _runtime_zero_touch_enabled() -> bool:
    """Enable automatic bootstrap only for managed runtimes unless the host overrides it."""
    if "MANGOME_ZERO_TOUCH_BOOTSTRAP" in os.environ:
        return _truthy_env("MANGOME_ZERO_TOUCH_BOOTSTRAP")
    return bool(
        os.environ.get("MANGOME_DEPLOYMENT_ID", "").strip()
        or os.environ.get("MANGOME_EXPECTED_VERSION", "").strip()
        or _truthy_env("MANGOME_AUTO_ATTACH")
    )

def database_binding_snapshot() -> dict[str, object]:
    backend = os.environ.get("MANGOME_BACKEND", "mongo").lower()
    if backend == "memory":
        return {
            "backend": "memory",
            "database": None,
            "expected_database": None,
            "source": "MEMORY",
            "state": "BOUND",
            "legacy_eval": False,
        }
    configured = os.environ.get("MANGOME_DATABASE", "mangome").strip() or "mangome"
    expected = os.environ.get("MANGOME_EXPECTED_DATABASE", "").strip() or configured
    legacy_eval = configured in _LEGACY_EVAL_DATABASES
    allow_eval = _truthy_env("MANGOME_ALLOW_EVAL_DATABASE")
    adopted_existing = _truthy_env("MANGOME_ADOPT_EXISTING_DATABASE")
    if configured != expected:
        state = "MISMATCH"
    elif legacy_eval and not allow_eval and not adopted_existing:
        state = "LEGACY_EVAL_REQUIRES_OPT_IN"
    elif legacy_eval and adopted_existing:
        state = "ADOPTED_EXISTING_DATABASE"
    else:
        state = "BOUND"
    return {
        "backend": "mongodb",
        "database": configured,
        "expected_database": expected,
        "source": "MANGOME_DATABASE" if "MANGOME_DATABASE" in os.environ else "DEFAULT_MANGOME",
        "state": state,
        "legacy_eval": legacy_eval,
        "eval_opt_in": allow_eval,
        "adopted_existing_database": adopted_existing,
        "rule": "DATABASE_IDENTITY_IS_DEPLOYMENT_STATE; EXISTING_VERIFIED_BINDINGS_SURVIVE_UPGRADES",
    }


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


def database_bootstrap_snapshot() -> dict[str, object]:
    """Return sanitized process-local zero-touch bootstrap state."""
    if _database_bootstrap_snapshot is not None:
        return dict(_database_bootstrap_snapshot)
    return {
        "status": "NOT_ATTEMPTED",
        "attempted": _database_bootstrap_attempted,
        "automatic_runtime_bootstrap_enabled": _runtime_zero_touch_enabled(),
        "rule": "ZERO_TOUCH_BOOTSTRAP_RUNS_ON_FIRST_DATABASE_ACCESS_FOR_MANAGED_RUNTIMES",
    }


def _bootstrap_database_once(database: str) -> dict[str, object]:
    """Run zero-touch MongoDB adoption/bootstrap at most once per process.

    This closes the installation/runtime gap: a managed MCP process must not depend
    on the user or agent remembering to run ``mangome setup`` first.  The bounded
    bootstrap may adopt an already-authorized credential source and create declared
    MongoDB indexes; it never creates users/roles or runs MangoMe schema migrations.
    """
    global _database_bootstrap_attempted, _database_bootstrap_snapshot, _database_bootstrap_error

    if os.environ.get("MANGOME_BACKEND", "mongo").strip().lower() == "memory":
        _database_bootstrap_snapshot = {"status": "NOT_APPLICABLE", "attempted": False, "database": None}
        return dict(_database_bootstrap_snapshot)

    if _database_bootstrap_error is not None:
        code, message = _database_bootstrap_error
        raise OperabilityError(code, message)
    if _database_bootstrap_snapshot is not None and _database_bootstrap_attempted:
        return dict(_database_bootstrap_snapshot)

    _database_bootstrap_attempted = True
    try:
        from .zero_touch import ZeroTouchBootstrapError, prepare_mongodb_runtime

        workspace = os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd()
        result = prepare_mongodb_runtime(workspace, database=database)
        _database_bootstrap_snapshot = {
            **result,
            "attempted": True,
            "runtime_trigger": "MANAGED_STARTUP_OR_FIRST_DATABASE_ACCESS",
        }
        return dict(_database_bootstrap_snapshot)
    except ZeroTouchBootstrapError as exc:
        _database_bootstrap_error = (exc.code, str(exc))
        _database_bootstrap_snapshot = {
            "status": "BLOCKED",
            "attempted": True,
            "database": database,
            "reason_code": exc.code,
            "restart_required_after_repair": True,
            "rule": "ZERO_TOUCH_FAILURE_IS_CACHED_PER_PROCESS_TO_PREVENT_RETRY_LOOPS",
        }
        raise OperabilityError(exc.code, str(exc)) from exc
    except Exception as exc:
        code = "ZERO_TOUCH_BOOTSTRAP_FAILED"
        message = "zero-touch MongoDB bootstrap failed before MangoMe service initialization"
        _database_bootstrap_error = (code, message)
        _database_bootstrap_snapshot = {
            "status": "BLOCKED",
            "attempted": True,
            "database": database,
            "reason_code": code,
            "error_type": type(exc).__name__,
            "restart_required_after_repair": True,
            "rule": "ZERO_TOUCH_FAILURE_IS_CACHED_PER_PROCESS_TO_PREVENT_RETRY_LOOPS",
        }
        raise OperabilityError(code, message) from exc


def get_service() -> MangoMeService:
    global _service, _workspace_attachment, _session_restore
    if _service is not None:
        return _service
    enforce_expected_identity()
    backend = os.environ.get("MANGOME_BACKEND", "mongo").lower()

    if backend == "memory":
        store = InMemoryStore()
    else:
        # Bootstrap precedes database-name rejection. During an upgrade, zero-touch
        # may prove that an existing deployment database (including a historically
        # eval-named database) is the real durable MangoMe state. Installation must
        # preserve that identity rather than forcing a fresh default database.
        initial = database_binding_snapshot()
        requested_database = str(initial.get("database") or "mangome")
        if _runtime_zero_touch_enabled():
            _bootstrap_database_once(requested_database)

        # Zero-touch may have adopted/persisted an existing database identity and
        # updated the process environment. Recompute before constructing the store.
        binding = database_binding_snapshot()
        database = str(binding.get("database") or requested_database)
        expected_database = str(binding.get("expected_database") or database)
        if binding.get("state") == "MISMATCH":
            raise OperabilityError(
                "WRONG_MANGOME_DATABASE",
                f"managed MangoMe binding expects database {expected_database!r}, running configuration selects {database!r}",
            )
        if binding.get("state") == "LEGACY_EVAL_REQUIRES_OPT_IN":
            raise OperabilityError(
                "LEGACY_EVAL_DATABASE_REQUIRES_OPT_IN",
                "legacy eval database is allowed only when explicitly requested or when zero-touch has proven it is the existing deployment database",
            )
        mongo = resolve_mongodb_connection()
        store = MongoStore(mongo.uri, database)
        enforce_mongo_role_boundary(store)

    _service = WorkGovernedMangoMeService(store)
    if os.environ.get("MANGOME_AUTO_ATTACH", "").strip().lower() in {"1", "true", "yes", "on"}:
        # Startup binding must remain cheap and non-blocking. Discovery and canonical
        # recovery are explicit/lazy even after database identity adoption.
        _workspace_attachment = bind_workspace_read_only(os.environ.get("MANGOME_WORKSPACE_ROOT"))
    return _service



def set_session_restore_snapshot(value: dict[str, object] | None) -> None:
    global _session_restore
    _session_restore = value


def session_restore_snapshot() -> dict[str, object] | None:
    return _session_restore

def workspace_attachment_snapshot() -> dict[str, object] | None:
    return _workspace_attachment


def _path_relation(current: Path, candidate: Path) -> tuple[str, int] | None:
    """Return canonical path relation without touching the filesystem beyond normalization."""
    if current == candidate:
        return ("EXACT", 0)
    try:
        rel = current.relative_to(candidate)
        return ("CANONICAL_ANCESTOR", len(rel.parts))
    except ValueError:
        pass
    try:
        rel = candidate.relative_to(current)
        return ("CANONICAL_DESCENDANT", len(rel.parts))
    except ValueError:
        return None


def _canonical_workspace_resolution(service: MangoMeService, workspace_root: str) -> dict[str, object]:
    """Resolve an already-admitted workspace from canonical MangoMe state only.

    The exact path hash remains primary.  This fallback exists for clients such as
    Codex that may start outside a saved project and therefore present a parent or
    child cwd.  It never scans the filesystem, host memory, contracts or Git.
    """
    current = Path(workspace_root).expanduser().resolve()
    by_project: dict[str, dict[str, object]] = {}
    for family in service.store.find("families"):
        scope_ids = list(family.get("scope_ids") or [])
        workspace_ids = [str(value)[10:] for value in scope_ids if str(value).startswith("workspace:")]
        if not workspace_ids:
            continue
        for workspace_id in workspace_ids:
            try:
                candidate = Path(workspace_id).expanduser().resolve()
            except OSError:
                continue
            relation = _path_relation(current, candidate)
            if relation is None:
                continue
            relation_name, distance = relation
            rank = {"EXACT": 0, "CANONICAL_ANCESTOR": 1, "CANONICAL_DESCENDANT": 2}[relation_name]
            for project_id in list(family.get("project_ids") or []):
                project = service.store.get("projects", project_id)
                if not project:
                    continue
                project_key = str(project.get("project_key") or "")
                if not project_key:
                    continue
                item = {
                    "project_id": project_id,
                    "project_key": project_key,
                    "canonical_workspace_id": workspace_id,
                    "relation": relation_name,
                    "distance": distance,
                    "rank": rank,
                }
                previous = by_project.get(project_key)
                if previous is None or (rank, distance) < (int(previous["rank"]), int(previous["distance"])):
                    by_project[project_key] = item

    candidates = sorted(by_project.values(), key=lambda row: (int(row["rank"]), int(row["distance"]), str(row["project_key"])))
    if not candidates:
        return {"state": "NO_CANONICAL_CANDIDATE", "candidate_count": 0, "candidates": []}

    best_rank = int(candidates[0]["rank"])
    best_distance = int(candidates[0]["distance"])
    best = [row for row in candidates if int(row["rank"]) == best_rank and int(row["distance"]) == best_distance]
    # A descendant candidate is safe only when it is the single canonical project
    # below the broad cwd. Multiple descendants are deliberately ambiguous.
    if best_rank == 2 and len(candidates) != 1:
        return {
            "state": "AMBIGUOUS",
            "candidate_count": len(candidates),
            "candidates": candidates[:10],
            "rule": "A broad client cwd may cover multiple canonical MangoMe workspaces; never guess which one the user means.",
        }
    if len(best) != 1:
        return {
            "state": "AMBIGUOUS",
            "candidate_count": len(candidates),
            "candidates": candidates[:10],
            "rule": "Multiple equally specific canonical workspace bindings exist; explicit target selection is required.",
        }
    return {"state": "RESOLVED", "candidate_count": len(candidates), "selected": best[0], "candidates": candidates[:10]}


def restore_workspace_state(workspace_root: str | None = None) -> dict[str, object]:
    """Read canonical recovery state using only canonical DB identity and workspace state.

    Exact workspace identity wins. If a client starts outside its saved project,
    MangoMe may re-bind read-only to one unambiguous canonical workspace already
    present in the same database. No filesystem discovery, host memory, Git or new
    canonical state is used to manufacture recovery.
    """
    current = ensure_workspace_binding(workspace_root) if workspace_root is not None else (workspace_attachment_snapshot() or ensure_workspace_binding())
    root = str((current or {}).get("workspace_root") or workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    service = get_service()
    exact_project_key = workspace_project_key(root)
    result = service.session_restore(exact_project_key)
    resolution: dict[str, object] = {
        "requested_workspace_root": root,
        "requested_project_key": exact_project_key,
        "state": "EXACT",
    }

    if result.get("restore_state") == "STATE_NOT_FOUND":
        fallback = _canonical_workspace_resolution(service, root)
        if fallback.get("state") == "RESOLVED":
            selected = dict(fallback.get("selected") or {})
            project_key = str(selected.get("project_key") or "")
            resolved = service.session_restore(project_key)
            if resolved.get("restore_state") != "STATE_NOT_FOUND":
                result = resolved
                resolution = {
                    **fallback,
                    "state": "CANONICAL_REBOUND",
                    "requested_workspace_root": root,
                    "requested_project_key": exact_project_key,
                    "resolved_project_key": project_key,
                    "resolved_workspace_root": selected.get("canonical_workspace_id"),
                    "rule": "Recovery followed canonical MangoMe workspace identity already present in the configured database; no discovery or admission occurred.",
                }
        elif fallback.get("state") == "AMBIGUOUS":
            result = {
                "restore_state": "STATE_PARTIAL",
                "source": "MANGOME_CANONICAL_STATE",
                "project_ref": exact_project_key,
                "productive_execution_allowed": False,
                "recovery_only_allowed": True,
                "next_executable_items": [],
                "reason_codes": ["WORKSPACE_BINDING_AMBIGUOUS"],
                "rule": "Canonical state exists for multiple candidate workspaces; never manufacture or guess the current identity.",
            }
            resolution = {
                **fallback,
                "requested_workspace_root": root,
                "requested_project_key": exact_project_key,
            }
        else:
            resolution = {
                **fallback,
                "requested_workspace_root": root,
                "requested_project_key": exact_project_key,
            }

    result["workspace_resolution"] = resolution
    result["database_binding"] = database_binding_snapshot()
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


def _trust_boundary_snapshot() -> dict[str, object] | None:
    if os.environ.get("MANGOME_BACKEND", "mongo").lower() == "memory":
        return None
    try:
        return dict(resolve_mongodb_connection().status)
    except Exception as exc:
        return {
            "protocol": "MTB/1",
            "mode": os.environ.get("MANGOME_TRUST_BOUNDARY", "WARN").strip().upper(),
            "ok": False,
            "reason_code": getattr(exc, "code", type(exc).__name__),
        }


def health_snapshot() -> dict[str, object]:
    """Return sanitized readiness, including zero-touch bootstrap state.

    The trust-boundary snapshot is intentionally computed *after* ``get_service``
    gets a chance to run zero-touch adoption.  Otherwise the same HEALTH response can
    report a recovered database while still describing the pre-recovery credential
    source, which is misleading.
    """
    from . import __version__
    from .schema import CURRENT_SCHEMA_VERSION

    backend = os.environ.get("MANGOME_BACKEND", "mongo").lower()
    binding = database_binding_snapshot()
    database = binding.get("database") if backend != "memory" else None
    backend_name = "memory" if backend == "memory" else "mongodb"

    try:
        service = get_service()
        store_health = service.store.health()
        binding = database_binding_snapshot()
        database = binding.get("database") if backend != "memory" else None
    except Exception as exc:  # health must survive failed store/bootstrap initialization
        # Bootstrap may have changed the effective database identity before failing.
        # Always report the post-bootstrap binding rather than stale preflight state.
        binding = database_binding_snapshot()
        database = binding.get("database") if backend != "memory" else None
        error_type = type(exc).__name__
        code = getattr(exc, "code", None)
        if code == "BOOTSTRAP_AUTHORITY_REQUIRED":
            diagnostic = "MongoDB bootstrap authority is unavailable"
        elif code == "MONGODB_UNREACHABLE":
            diagnostic = "MongoDB is unreachable during zero-touch bootstrap"
        elif code == "DATABASE_BOOTSTRAP_FAILED":
            diagnostic = "MongoDB zero-touch database bootstrap failed"
        elif code == "ZERO_TOUCH_BOOTSTRAP_FAILED":
            diagnostic = "MangoMe zero-touch bootstrap failed before service initialization"
        elif isinstance(exc, OperabilityError):
            diagnostic = "MangoMe client/runtime identity or deployment binding failed"
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
            "process_ready": True,
            "database_ready": False,
            "version": __version__,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "database_binding": binding,
            "database_bootstrap": database_bootstrap_snapshot(),
            "store": store,
            "trust_boundary": _trust_boundary_snapshot(),
            "workspace_attachment": _workspace_attachment,
        }

    return {
        "ok": bool(store_health.get("ok")),
        "process_ready": True,
        "database_ready": bool(store_health.get("ok")),
        "version": __version__,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "database_binding": binding,
        "database_bootstrap": database_bootstrap_snapshot(),
        "store": store_health,
        "trust_boundary": _trust_boundary_snapshot(),
        "workspace_attachment": _workspace_attachment,
    }


def reset_service_for_tests() -> None:
    """Reset process-global service/bootstrap state. Intended for tests only."""
    global _service, _workspace_attachment, _session_restore
    global _database_bootstrap_attempted, _database_bootstrap_snapshot, _database_bootstrap_error
    _service = None
    _workspace_attachment = None
    _session_restore = None
    _database_bootstrap_attempted = False
    _database_bootstrap_snapshot = None
    _database_bootstrap_error = None
