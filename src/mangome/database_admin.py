from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, urlsplit

from .storage.mongo import MongoStore
from .zero_touch import (
    ZeroTouchBootstrapError,
    _collect_candidates,
    _read_uri_file,
    _secure_managed_database_binding,
)


DATABASE_RESET_CONFIRMATION = "TOTAL-RESET-MANGOME-DATABASES"
CANONICAL_DATABASE = "mangome"
LEGACY_EVAL_DATABASE = "mangome_uai_eval"
RESET_DATABASES = (CANONICAL_DATABASE, LEGACY_EVAL_DATABASE)
RUNTIME_USER = "mangome_runtime"


class DatabaseResetError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def database_reset_warning() -> dict[str, Any]:
    return {
        "ok": False,
        "warning": "DESTRUCTIVE_DATABASE_RESET",
        "message": (
            "This permanently resets only the explicitly allowlisted MangoMe databases. "
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
            "runtime_user": RUNTIME_USER,
            "roles": [{"role": "readWrite", "db": CANONICAL_DATABASE}],
            "credential_file": "~/.config/mangome/mongodb-uri",
            "database_binding": "~/.config/mangome/database-binding.json",
        },
        "safety": {
            "shared_mongodb_service_restart": False,
            "wildcard_database_matching": False,
            "offline_noauth_bootstrap": False,
            "fail_closed_without_online_maintenance_authority": True,
        },
        "confirmation_required": DATABASE_RESET_CONFIRMATION,
        "example": (
            "mangome database-reset --confirm "
            + DATABASE_RESET_CONFIRMATION
        ),
    }


def _looks_like_mongodb_uri(value: str) -> bool:
    text = str(value or "").strip()
    return text.startswith("mongodb://") or text.startswith("mongodb+srv://")


def _auth_source(uri: str) -> str:
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return ""
    query = parse_qs(parsed.query)
    explicit = str((query.get("authSource") or [""])[0]).strip()
    if explicit:
        return explicit
    database = parsed.path.lstrip("/").split("/", 1)[0].strip()
    return database or "admin"


def _stage_runtime_credential(home: Path, uri: str) -> tuple[Path, Path]:
    if not _looks_like_mongodb_uri(uri):
        raise DatabaseResetError(
            "DATABASE_RESET_CREDENTIAL_INVALID",
            "generated runtime MongoDB URI is invalid",
        )
    directory = home / ".config" / "mangome"
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        target = directory / "mongodb-uri"
        if target.is_symlink():
            raise DatabaseResetError(
                "DATABASE_RESET_CREDENTIAL_TARGET_UNSAFE",
                "managed MongoDB credential target must not be a symlink",
            )
        staged = directory / ".mongodb-uri.reset.pending"
        if staged.is_symlink():
            staged.unlink()
        fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(uri.strip() + "\n")
        os.chmod(staged, 0o600)
        info = staged.stat()
        if not stat.S_ISREG(info.st_mode):
            raise DatabaseResetError(
                "DATABASE_RESET_CREDENTIAL_STAGE_UNSAFE",
                "staged MongoDB credential is not a regular file",
            )
        return staged, target
    except DatabaseResetError:
        raise
    except OSError as exc:
        raise DatabaseResetError(
            "DATABASE_RESET_CREDENTIAL_STAGE_FAILED",
            "cannot stage the fresh MangoMe runtime credential",
        ) from exc


def _commit_runtime_credential(staged: Path, target: Path) -> Path:
    try:
        os.replace(staged, target)
        os.chmod(target, 0o600)
        return target.resolve()
    except OSError as exc:
        raise DatabaseResetError(
            "DATABASE_RESET_CREDENTIAL_COMMIT_FAILED",
            "fresh MangoMe runtime credential could not be committed",
        ) from exc


def _explicit_maintenance_candidates(home: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    file_value = os.environ.get("MANGOME_MONGODB_MAINTENANCE_URI_FILE", "").strip()
    uri_value = os.environ.get("MANGOME_MONGODB_MAINTENANCE_URI", "").strip()

    file_candidates: list[tuple[str, str]] = []
    if file_value:
        file_candidates.append(("MANGOME_MONGODB_MAINTENANCE_URI_FILE", file_value))

    managed_maintenance = home / ".config" / "mangome" / "mongodb-maintenance-uri"
    if managed_maintenance.is_file() and not managed_maintenance.is_symlink():
        file_candidates.append(("MANAGED_MAINTENANCE_CREDENTIAL_FILE", str(managed_maintenance)))

    for source, path in file_candidates:
        try:
            out.append((source, _read_uri_file(path)))
        except ZeroTouchBootstrapError:
            continue

    if _looks_like_mongodb_uri(uri_value):
        out.append(("MANGOME_MONGODB_MAINTENANCE_URI", uri_value))
    return out


def _candidate_uris(workspace: Path, home: Path) -> list[tuple[str, str]]:
    out = _explicit_maintenance_candidates(home)
    try:
        discovered = _collect_candidates(workspace, home)
    except Exception:
        discovered = []
    for candidate in discovered:
        try:
            uri = _read_uri_file(candidate.value) if candidate.kind == "FILE" else str(candidate.value).strip()
        except Exception:
            continue
        if _looks_like_mongodb_uri(uri):
            out.append((str(candidate.source), uri))

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source, uri in out:
        if uri in seen:
            continue
        seen.add(uri)
        deduped.append((source, uri))
    return deduped


def _privilege_matches_database(resource: dict[str, Any], database: str) -> bool:
    if bool(resource.get("anyResource")):
        return True
    resource_db = str(resource.get("db") or "")
    collection = str(resource.get("collection") or "")
    return resource_db == database and collection == ""


def _has_action(privileges: Iterable[dict[str, Any]], database: str, action: str) -> bool:
    wanted = str(action)
    for privilege in privileges:
        if not isinstance(privilege, dict):
            continue
        resource = privilege.get("resource") or {}
        actions = {str(item) for item in (privilege.get("actions") or [])}
        if wanted in actions and isinstance(resource, dict) and _privilege_matches_database(resource, database):
            return True
    return False


def _maintenance_authority(uri: str) -> tuple[bool, dict[str, Any]]:
    # The credential performing the reset must survive dropping both target DBs.
    if _auth_source(uri) in RESET_DATABASES:
        return False, {"reason": "AUTHORITY_USER_LIVES_IN_RESET_DATABASE"}

    store: MongoStore | None = None
    try:
        store = MongoStore(uri, "admin")
        status = store.client.admin.command({"connectionStatus": 1, "showPrivileges": True})
        auth_info = status.get("authInfo") or {}
        privileges = auth_info.get("authenticatedUserPrivileges") or []
        roles = auth_info.get("authenticatedUserRoles") or []
        requirements = {
            CANONICAL_DATABASE: {"dropDatabase", "dropUser", "createUser"},
            LEGACY_EVAL_DATABASE: {"dropDatabase", "dropUser"},
        }
        missing: dict[str, list[str]] = {}
        for database, actions in requirements.items():
            absent = sorted(
                action for action in actions
                if not _has_action(privileges, database, action)
            )
            if absent:
                missing[database] = absent
        return not missing, {"roles": roles, "missing_actions": missing}
    except Exception as exc:
        return False, {"reason": type(exc).__name__}
    finally:
        if store is not None:
            try:
                store.client.close()
            except Exception:
                pass


def _select_online_maintenance_uri(workspace: Path, home: Path) -> tuple[str, str]:
    for source, uri in _candidate_uris(workspace, home):
        ok, _detail = _maintenance_authority(uri)
        if ok:
            return source, uri
    raise DatabaseResetError(
        "DATABASE_RESET_AUTHORITY_REQUIRED",
        (
            "no already-available online MongoDB credential with authority over exactly "
            "mangome and mangome_uai_eval was discovered; no database was modified and "
            "the shared MongoDB service was left running"
        ),
    )


def _database_names_if_allowed(store: MongoStore) -> set[str] | None:
    try:
        return set(store.client.list_database_names())
    except Exception:
        return None


def _verify_runtime(uri: str) -> dict[str, Any]:
    store = MongoStore(uri, CANONICAL_DATABASE)
    try:
        store.db.command("ping")
        store.ensure_indexes()
        status = store.db.command("connectionStatus")
        roles = [
            {"role": str(item.get("role")), "db": str(item.get("db"))}
            for item in ((status.get("authInfo") or {}).get("authenticatedUserRoles") or [])
            if isinstance(item, dict)
        ]
        expected = [{"role": "readWrite", "db": CANONICAL_DATABASE}]
        if roles != expected:
            raise DatabaseResetError(
                "DATABASE_RESET_ROLE_VERIFY_FAILED",
                "fresh mangome_runtime does not have exactly readWrite on mangome",
            )
        return {
            "database_ready": True,
            "canonical_indexes_ready": True,
            "runtime_role_verified": True,
            "runtime_roles": roles,
        }
    except DatabaseResetError:
        raise
    except Exception as exc:
        raise DatabaseResetError(
            "DATABASE_RESET_VERIFY_FAILED",
            f"fresh MangoMe runtime could not be verified ({type(exc).__name__})",
        ) from exc
    finally:
        store.client.close()


def _runtime_endpoint(authority_uri: str) -> tuple[str, int]:
    try:
        parsed = urlsplit(authority_uri)
    except ValueError as exc:
        raise DatabaseResetError(
            "DATABASE_RESET_AUTHORITY_URI_INVALID",
            "maintenance MongoDB URI is invalid",
        ) from exc
    if parsed.scheme != "mongodb":
        raise DatabaseResetError(
            "DATABASE_RESET_AUTHORITY_URI_UNSUPPORTED",
            "database-reset currently requires a direct mongodb:// maintenance endpoint",
        )
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 27017
    if host in {"localhost", "::1"}:
        host = "127.0.0.1"
    return host, port


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

    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    workspace_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd().resolve()

    # P0 invariant: obtain sufficient ONLINE authority before any mutation. There is
    # deliberately no systemctl stop/start, no temporary --noauth mongod and no dbPath access.
    authority_source, authority_uri = _select_online_maintenance_uri(workspace_path, home_path)
    host, port = _runtime_endpoint(authority_uri)
    authority = MongoStore(authority_uri, "admin")
    before = _database_names_if_allowed(authority)

    password = secrets.token_urlsafe(36)
    encoded_user = quote(RUNTIME_USER, safe="")
    encoded_password = quote(password, safe="")
    encoded_db = quote(CANONICAL_DATABASE, safe="")
    runtime_uri = (
        f"mongodb://{encoded_user}:{encoded_password}@{host}:{port}/"
        f"{encoded_db}?authSource={encoded_db}"
    )

    # Stage locally before touching MongoDB; commit only after the new runtime user verifies.
    staged, credential_target = _stage_runtime_credential(home_path, runtime_uri)
    dropped_databases: list[str] = []

    try:
        for name in RESET_DATABASES:
            existed = before is None or name in before
            if not existed:
                continue
            db = authority.client[name]
            db.command({"dropAllUsersFromDatabase": 1})
            result = db.command({"dropDatabase": 1})
            if before is not None:
                dropped_databases.append(name)
            elif str(result.get("dropped") or "") == name:
                dropped_databases.append(name)

        fresh = authority.client[CANONICAL_DATABASE]
        fresh.command({
            "createUser": RUNTIME_USER,
            "pwd": password,
            "roles": [{"role": "readWrite", "db": CANONICAL_DATABASE}],
        })

        verification = _verify_runtime(runtime_uri)
        credential_path = _commit_runtime_credential(staged, credential_target)
        _secure_managed_database_binding(
            home_path,
            database=CANONICAL_DATABASE,
            source="DATABASE_TOTAL_RESET_ONLINE",
            adopted_existing=False,
        )

        after = _database_names_if_allowed(authority)
        preserved_verified: bool | None = None
        if before is not None and after is not None:
            preserved_verified = (before - set(RESET_DATABASES)) == (after - set(RESET_DATABASES))
            if not preserved_verified:
                raise DatabaseResetError(
                    "DATABASE_RESET_PRESERVATION_VERIFY_FAILED",
                    "a non-target MongoDB database changed during reset verification",
                )

        os.environ["MANGOME_MONGODB_URI_FILE"] = str(credential_path)
        os.environ.pop("MANGOME_MONGODB_URI", None)
        os.environ["MANGOME_DATABASE"] = CANONICAL_DATABASE
        os.environ["MANGOME_EXPECTED_DATABASE"] = CANONICAL_DATABASE
        os.environ.pop("MANGOME_ALLOW_EVAL_DATABASE", None)
        os.environ.pop("MANGOME_ADOPT_EXISTING_DATABASE", None)

        return {
            "ok": True,
            "operation": "DATABASE_TOTAL_RESET",
            "destructive": True,
            "scope": "EXACT_DATABASE_ALLOWLIST",
            "allowlist": list(RESET_DATABASES),
            "dropped_databases": dropped_databases,
            "database": CANONICAL_DATABASE,
            "legacy_eval_database_removed": (
                before is not None
                and LEGACY_EVAL_DATABASE in before
                and after is not None
                and LEGACY_EVAL_DATABASE not in after
            ),
            "runtime_user": RUNTIME_USER,
            "runtime_role": {"role": "readWrite", "db": CANONICAL_DATABASE},
            "credential_file": str(credential_path),
            "database_binding": str(home_path / ".config" / "mangome" / "database-binding.json"),
            "maintenance_authority_source": authority_source,
            "database_migration_performed": False,
            "shared_mongodb_service_restarted": False,
            "offline_noauth_bootstrap_used": False,
            "wildcard_database_matching_used": False,
            "non_target_databases_preservation_verified": preserved_verified,
            "mcp_restart_required": True,
            **verification,
        }
    finally:
        authority.client.close()
        if staged.exists():
            try:
                staged.unlink()
            except OSError:
                pass
