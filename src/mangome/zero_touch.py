from __future__ import annotations

from pathlib import Path
from typing import Any

from .operability import OperabilityError
from .storage.mongo import MongoStore
from .trust_boundary import enforce_mongo_role_boundary, resolve_mongodb_connection

ZERO_TOUCH_BOOTSTRAP_SCOPE = "LOCAL_HOST_TRUST_READINESS_ONLY"
CANONICAL_DATABASE = "mangome"
LEGACY_DATABASES = {"mangome_uai_eval"}


class ZeroTouchBootstrapError(RuntimeError):
    """Fail-closed local-host bootstrap error with a stable operator-facing code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _map_failure(exc: Exception) -> ZeroTouchBootstrapError:
    if isinstance(exc, ZeroTouchBootstrapError):
        return exc
    if isinstance(exc, OperabilityError):
        return ZeroTouchBootstrapError(exc.code, str(exc))
    code = getattr(exc, "code", None)
    name = type(exc).__name__
    if code in {13, 18} or name in {"AuthenticationFailure", "OperationFailure"}:
        return ZeroTouchBootstrapError(
            "LOCAL_HOST_MONGODB_AUTHORIZATION_ENABLED",
            "MongoDB authorization is enabled; LOCAL_HOST requires loopback-only unauthenticated MongoDB",
        )
    if name in {"ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect", "NetworkTimeout"}:
        return ZeroTouchBootstrapError("MONGODB_UNREACHABLE", "MongoDB is unreachable from MangoMe")
    return ZeroTouchBootstrapError(
        "LOCAL_HOST_BOOTSTRAP_FAILED",
        f"LOCAL_HOST readiness failed ({name})",
    )


def prepare_mongodb_runtime(
    workspace_root: str | Path,
    *,
    database: str = CANONICAL_DATABASE,
    home: str | None = None,
) -> dict[str, Any]:
    """Validate the v0.3.14 zero-touch single-host runtime.

    There is deliberately no credential discovery/adoption, no MongoDB user/role
    creation, no maintenance principal, no systemd manipulation, no temporary
    --noauth mongod and no database identity migration.

    Legacy databases are never adopted, repaired or migrated. Selecting a legacy
    database fails closed because schema drift cannot be assumed safe.
    """

    requested_database = str(database or CANONICAL_DATABASE).strip() or CANONICAL_DATABASE
    if requested_database in LEGACY_DATABASES:
        raise ZeroTouchBootstrapError(
            "LEGACY_DATABASE_SCHEMA_DRIFT",
            f"legacy database {requested_database!r} is rejected; automatic repair/adoption/migration is forbidden",
        )
    if requested_database != CANONICAL_DATABASE:
        raise ZeroTouchBootstrapError(
            "WRONG_MANGOME_DATABASE",
            f"managed MangoMe v0.3.14 requires database {CANONICAL_DATABASE!r}, got {requested_database!r}",
        )

    store: MongoStore | None = None
    try:
        config = resolve_mongodb_connection()
        store = MongoStore(config.uri, CANONICAL_DATABASE)
        store.db.command("ping")
        enforce_mongo_role_boundary(store)
        store.ensure_indexes()
        return {
            "status": "READY",
            "database": CANONICAL_DATABASE,
            "requested_database": requested_database,
            "database_ready": True,
            "canonical_indexes_ready": True,
            "credential_source": "NONE",
            "credential_file_bound": False,
            "local_runtime_user_provisioned": False,
            "existing_database_identity_adopted": False,
            "database_migration_performed": False,
            "bootstrap_scope": ZERO_TOUCH_BOOTSTRAP_SCOPE,
            "canonical_domain_mutations": 0,
            "authorization_model": "HOST_LOCAL_ONLY",
            "rule": "LOOPBACK_ONLY; NO_CREDENTIAL_ADOPTION; LEGACY_DATABASES_ARE_NEVER_AUTO_REPAIRED",
        }
    except Exception as exc:
        mapped = _map_failure(exc)
        if mapped is exc:
            raise
        raise mapped from exc
    finally:
        if store is not None:
            try:
                store.client.close()
            except Exception:
                pass
