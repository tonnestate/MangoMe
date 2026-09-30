from __future__ import annotations

from typing import Any

from .operability import OperabilityError
from .storage.mongo import MongoStore
from .trust_boundary import enforce_mongo_role_boundary, resolve_mongodb_connection

DATABASE_RESET_CONFIRMATION = "TOTAL-RESET-MANGOME-DATABASES"
CANONICAL_DATABASE = "mangome"
LEGACY_EVAL_DATABASE = "mangome_uai_eval"
RESET_DATABASES = (CANONICAL_DATABASE, LEGACY_EVAL_DATABASE)


class DatabaseResetError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def database_reset_warning() -> dict[str, Any]:
    return {
        "ok": False,
        "warning": "DESTRUCTIVE_DATABASE_RESET",
        "message": (
            "LOCAL_HOST reset permanently deletes only the exact MangoMe database allowlist. "
            "The shared MongoDB service is never stopped or restarted."
        ),
        "database_scope": {
            "targets": list(RESET_DATABASES),
            "preserved": [
                "admin",
                "config",
                "local",
                "every database not explicitly listed in targets",
            ],
        },
        "recreated": {
            "database": CANONICAL_DATABASE,
            "runtime_user": None,
            "roles": [],
            "authorization_model": "HOST_LOCAL_ONLY",
        },
        "legacy_policy": {
            "runtime_adoption": False,
            "automatic_repair": False,
            "automatic_migration": False,
            "explicit_reset_may_delete": [LEGACY_EVAL_DATABASE],
            "reason": "SCHEMA_DRIFT_FAIL_CLOSED",
        },
        "safety": {
            "shared_mongodb_service_restart": False,
            "wildcard_database_matching": False,
            "offline_noauth_bootstrap": False,
            "credential_or_role_bootstrap": False,
            "dbpath_access": False,
        },
        "confirmation_required": DATABASE_RESET_CONFIRMATION,
        "example": "mangome database-reset --confirm " + DATABASE_RESET_CONFIRMATION,
    }


def _map_error(exc: Exception) -> DatabaseResetError:
    if isinstance(exc, DatabaseResetError):
        return exc
    if isinstance(exc, OperabilityError):
        return DatabaseResetError(exc.code, str(exc))
    code = getattr(exc, "code", None)
    name = type(exc).__name__
    if code in {13, 18} or name in {"AuthenticationFailure", "OperationFailure"}:
        return DatabaseResetError(
            "LOCAL_HOST_MONGODB_AUTHORIZATION_ENABLED",
            "MongoDB authorization is enabled; reset requires verified LOCAL_HOST mode",
        )
    if name in {"ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect", "NetworkTimeout"}:
        return DatabaseResetError("MONGODB_UNREACHABLE", "MongoDB is unreachable from MangoMe")
    return DatabaseResetError("DATABASE_RESET_FAILED", f"database reset failed ({name})")


def total_reset_database(
    *,
    confirmation: str,
    home: str | None = None,
    workspace: str | None = None,
) -> dict[str, Any]:
    if confirmation != DATABASE_RESET_CONFIRMATION:
        raise DatabaseResetError(
            "DATABASE_RESET_CONFIRMATION_REQUIRED",
            f"exact confirmation required: {DATABASE_RESET_CONFIRMATION}",
        )

    authority: MongoStore | None = None
    fresh: MongoStore | None = None
    try:
        config = resolve_mongodb_connection()
        authority = MongoStore(config.uri, "admin")
        authority.client.admin.command("ping")

        # Fail before the first mutation unless loopback/no-auth LOCAL_HOST is proven.
        enforce_mongo_role_boundary(authority)
        before = set(authority.client.list_database_names())
        non_targets_before = before - set(RESET_DATABASES)

        dropped: list[str] = []
        for name in RESET_DATABASES:
            if name not in before:
                continue
            db = authority.client[name]
            # Remove any stale MangoMe-local users from older authenticated releases.
            # This never touches users in admin or in unrelated databases.
            db.command({"dropAllUsersFromDatabase": 1})
            db.command({"dropDatabase": 1})
            dropped.append(name)

        # Recreate only canonical MangoMe schema/index surfaces. No MongoDB user exists.
        fresh = MongoStore(config.uri, CANONICAL_DATABASE)
        fresh.ensure_indexes()
        fresh_health = fresh.health()
        enforce_mongo_role_boundary(fresh)

        after = set(authority.client.list_database_names())
        non_targets_after = after - set(RESET_DATABASES)
        if non_targets_before != non_targets_after:
            raise DatabaseResetError(
                "DATABASE_RESET_PRESERVATION_VERIFY_FAILED",
                "a non-target MongoDB database changed during reset verification",
            )

        if LEGACY_EVAL_DATABASE in after:
            raise DatabaseResetError(
                "LEGACY_DATABASE_RESET_VERIFY_FAILED",
                "legacy database still exists after explicit reset",
            )

        return {
            "ok": bool(fresh_health.get("ok")),
            "operation": "DATABASE_TOTAL_RESET",
            "destructive": True,
            "scope": "EXACT_DATABASE_ALLOWLIST",
            "allowlist": list(RESET_DATABASES),
            "dropped_databases": dropped,
            "database": CANONICAL_DATABASE,
            "legacy_eval_database_removed": LEGACY_EVAL_DATABASE not in after,
            "runtime_user": None,
            "runtime_roles": [],
            "authorization_model": "HOST_LOCAL_ONLY",
            "database_migration_performed": False,
            "legacy_database_adopted": False,
            "legacy_database_repaired": False,
            "shared_mongodb_service_restarted": False,
            "offline_noauth_bootstrap_used": False,
            "wildcard_database_matching_used": False,
            "credential_bootstrap_used": False,
            "non_target_databases_preservation_verified": True,
            "mcp_restart_required": True,
            "database_ready": True,
            "canonical_indexes_ready": True,
        }
    except Exception as exc:
        mapped = _map_error(exc)
        if mapped is exc:
            raise
        raise mapped from exc
    finally:
        if fresh is not None:
            try:
                fresh.client.close()
            except Exception:
                pass
        if authority is not None:
            try:
                authority.client.close()
            except Exception:
                pass
