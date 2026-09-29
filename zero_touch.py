from __future__ import annotations

import json
import os
import stat
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .storage.mongo import MongoStore


ZERO_TOUCH_BOOTSTRAP_SCOPE = "CREDENTIAL_ADOPTION_AND_DECLARED_INDEX_BOOTSTRAP_ONLY"


class ZeroTouchBootstrapError(RuntimeError):
    """Fail-closed zero-touch bootstrap error with a stable operator-facing code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _CredentialCandidate:
    source: str
    kind: str  # FILE | URI
    value: str
    legacy: bool = False


def _looks_like_mongodb_uri(value: str) -> bool:
    text = str(value or "").strip()
    return text.startswith("mongodb://") or text.startswith("mongodb+srv://")


def _candidate_from_env(source: str, env: dict[str, Any], *, legacy: bool) -> list[_CredentialCandidate]:
    out: list[_CredentialCandidate] = []
    file_value = str(env.get("MANGOME_MONGODB_URI_FILE") or "").strip()
    uri_value = str(env.get("MANGOME_MONGODB_URI") or "").strip()
    if file_value:
        out.append(_CredentialCandidate(source=f"{source}:FILE", kind="FILE", value=file_value, legacy=legacy))
    if _looks_like_mongodb_uri(uri_value):
        out.append(_CredentialCandidate(source=f"{source}:URI", kind="URI", value=uri_value, legacy=legacy))
    return out


def _codex_candidates(path: Path, *, legacy: bool) -> list[_CredentialCandidate]:
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    servers = data.get("mcp_servers") or {}
    if not isinstance(servers, dict):
        return []
    out: list[_CredentialCandidate] = []
    for name, entry in servers.items():
        if not str(name).lower().startswith("mangome") or not isinstance(entry, dict):
            continue
        env = entry.get("env") or {}
        if isinstance(env, dict):
            out.extend(_candidate_from_env(f"CODEX_CONFIG:{name}", env, legacy=legacy or str(name) != "mangome"))
    return out


def _claude_candidates(path: Path, *, legacy: bool) -> list[_CredentialCandidate]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []

    out: list[_CredentialCandidate] = []

    def collect(servers: Any, source: str) -> None:
        if not isinstance(servers, dict):
            return
        for name, entry in servers.items():
            if not str(name).lower().startswith("mangome") or not isinstance(entry, dict):
                continue
            env = entry.get("env") or {}
            if isinstance(env, dict):
                out.extend(_candidate_from_env(
                    f"{source}:{name}", env, legacy=legacy or str(name) != "mangome"
                ))

    collect(data.get("mcpServers"), "CLAUDE_CONFIG")
    projects = data.get("projects") or {}
    if isinstance(projects, dict):
        for project, project_data in projects.items():
            if isinstance(project_data, dict):
                collect(project_data.get("mcpServers"), f"CLAUDE_PROJECT:{project}")
    return out


def _live_process_candidates(proc_root: Path = Path("/proc")) -> list[_CredentialCandidate]:
    """Recover a legacy MangoMe MCP credential from its live process environment.

    The scan is intentionally process-name bounded. Values are never returned to the
    caller or logged; a successful URI is normalized into the managed credential file.
    """
    out: list[_CredentialCandidate] = []
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return out
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").lower()
        except OSError:
            continue
        if "mangome" not in cmdline:
            continue
        if not any(token in cmdline for token in ("mcp_server", "worker_mcp_server", "mangome-mcp", "mangome_eval")):
            continue
        try:
            raw = (entry / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        env: dict[str, str] = {}
        for item in raw:
            if b"=" not in item:
                continue
            key, value = item.split(b"=", 1)
            if key in {b"MANGOME_MONGODB_URI", b"MANGOME_MONGODB_URI_FILE"}:
                env[key.decode("ascii")] = value.decode("utf-8", "replace")
        if env:
            out.extend(_candidate_from_env("LIVE_MANGOME_PROCESS", env, legacy=True))
    return out


def _read_uri_file(path_value: str) -> str:
    path = Path(path_value).expanduser()
    try:
        info = path.stat()
    except OSError as exc:
        raise ZeroTouchBootstrapError("CREDENTIAL_SOURCE_UNREADABLE", "discovered MongoDB credential file is unreadable") from exc
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise ZeroTouchBootstrapError("CREDENTIAL_SOURCE_UNSAFE", "discovered MongoDB credential source is not a regular file")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise ZeroTouchBootstrapError("CREDENTIAL_SOURCE_UNSAFE", "discovered MongoDB credential file is not owned by the current service identity")
    try:
        uri = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ZeroTouchBootstrapError("CREDENTIAL_SOURCE_UNREADABLE", "discovered MongoDB credential file is unreadable") from exc
    if not _looks_like_mongodb_uri(uri):
        raise ZeroTouchBootstrapError("CREDENTIAL_SOURCE_INVALID", "discovered MongoDB credential file does not contain a MongoDB URI")
    return uri


def _secure_managed_credential_file(home: Path, uri: str) -> Path:
    if not _looks_like_mongodb_uri(uri):
        raise ZeroTouchBootstrapError("CREDENTIAL_SOURCE_INVALID", "MongoDB credential source is not a valid MongoDB URI")
    directory = home / ".config" / "mangome"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(directory, 0o700)
    except OSError as exc:
        raise ZeroTouchBootstrapError("CREDENTIAL_TARGET_UNWRITABLE", "cannot secure MangoMe credential directory") from exc
    target = directory / "mongodb-uri"
    if target.is_symlink():
        raise ZeroTouchBootstrapError("CREDENTIAL_TARGET_UNSAFE", "managed MongoDB credential target must not be a symlink")
    temp = directory / ".mongodb-uri.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    try:
        fd = os.open(temp, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(uri.strip() + "\n")
        os.chmod(temp, 0o600)
        os.replace(temp, target)
        os.chmod(target, 0o600)
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise ZeroTouchBootstrapError("CREDENTIAL_TARGET_UNWRITABLE", "cannot write managed MongoDB credential file") from exc
    return target.resolve()


def _classify_mongo_failure(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    name = type(exc).__name__
    if code in {13, 18} or name in {"AuthenticationFailure"}:
        return "AUTH"
    if name in {"ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect", "NetworkTimeout"}:
        return "UNREACHABLE"
    return "OTHER"


def _probe_uri(uri: str, database: str) -> dict[str, Any]:
    """Exercise the same canonical MongoDB requirement used by MangoMe runtime.

    `MangoMeService` creates indexes on startup, so zero-touch setup verifies that
    exact capability instead of accepting a credential that can merely ping MongoDB.
    This function is intentionally limited to declared index bootstrap plus ping; it
    does not create users/roles, run MangoMe schema migrations, or mutate domain rows.
    """
    store: MongoStore | None = None
    try:
        store = MongoStore(uri, database)
        store.ensure_indexes()
        store.db.command("ping")
        return {"database_ready": True, "canonical_indexes_ready": True}
    except Exception as exc:
        kind = _classify_mongo_failure(exc)
        if kind == "AUTH":
            raise ZeroTouchBootstrapError(
                "BOOTSTRAP_AUTHORITY_REQUIRED",
                "MongoDB is authentication-protected and no discovered credential authorizes the canonical MangoMe database",
            ) from exc
        if kind == "UNREACHABLE":
            raise ZeroTouchBootstrapError(
                "MONGODB_UNREACHABLE",
                "MongoDB is unreachable from the MangoMe setup process",
            ) from exc
        raise ZeroTouchBootstrapError(
            "DATABASE_BOOTSTRAP_FAILED",
            f"canonical MangoMe database bootstrap failed ({type(exc).__name__})",
        ) from exc
    finally:
        if store is not None:
            try:
                store.client.close()
            except Exception:
                pass


def _dedupe(candidates: Iterable[_CredentialCandidate]) -> list[_CredentialCandidate]:
    out: list[_CredentialCandidate] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        key = (item.kind, item.value)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _collect_candidates(workspace: Path, home: Path) -> list[_CredentialCandidate]:
    candidates: list[_CredentialCandidate] = []

    env = {
        "MANGOME_MONGODB_URI_FILE": os.environ.get("MANGOME_MONGODB_URI_FILE", ""),
        "MANGOME_MONGODB_URI": os.environ.get("MANGOME_MONGODB_URI", ""),
    }
    candidates.extend(_candidate_from_env("PROCESS_ENVIRONMENT", env, legacy=False))

    managed = home / ".config" / "mangome" / "mongodb-uri"
    if managed.is_file():
        candidates.append(_CredentialCandidate("MANAGED_CREDENTIAL_FILE", "FILE", str(managed), False))

    # A still-running legacy MCP process is often the only place where an older
    # launcher inherited a MongoDB credential without persisting it to client config.
    # Probe it before stale config/backups so startup does not spend multiple MongoDB
    # timeouts on obsolete candidates before reaching the most likely live authority.
    candidates.extend(_live_process_candidates())

    current_paths = [
        (home / ".codex" / "config.toml", "codex"),
        (workspace / ".codex" / "config.toml", "codex"),
        (home / ".claude.json", "claude"),
        (workspace / ".mcp.json", "claude"),
    ]
    backup_paths = [
        (home / ".codex" / "config.toml.mangome.bak", "codex"),
        (workspace / ".codex" / "config.toml.mangome.bak", "codex"),
        (home / ".claude.json.mangome.bak", "claude"),
        (workspace / ".mcp.json.mangome.bak", "claude"),
    ]
    for path, kind in [*current_paths, *backup_paths]:
        legacy = path.name.endswith(".mangome.bak")
        if kind == "codex":
            candidates.extend(_codex_candidates(path, legacy=legacy))
        else:
            candidates.extend(_claude_candidates(path, legacy=legacy))

    return _dedupe(candidates)


def prepare_mongodb_runtime(
    workspace_root: str | Path,
    *,
    database: str = "mangome",
    home: str | None = None,
) -> dict[str, Any]:
    """Zero-touch adoption/bootstrap for a managed MongoDB runtime.

    Existing environment, managed credential files, current/backup client bindings,
    and live legacy MangoMe MCP processes are treated as credential *sources only*.
    Secrets are never returned. A working source is normalized into an owner-only
    managed file before client configuration is rewritten.
    """
    workspace = Path(workspace_root).expanduser().resolve()
    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    candidates = _collect_candidates(workspace, home_path)
    failures: list[str] = []

    for candidate in candidates:
        try:
            uri = _read_uri_file(candidate.value) if candidate.kind == "FILE" else candidate.value.strip()
            probe = _probe_uri(uri, database)
        except ZeroTouchBootstrapError as exc:
            failures.append(exc.code)
            continue

        target = _secure_managed_credential_file(home_path, uri)
        os.environ["MANGOME_MONGODB_URI_FILE"] = str(target)
        # Once normalized, do not propagate a direct secret through child environments.
        os.environ.pop("MANGOME_MONGODB_URI", None)
        return {
            "status": "READY",
            "database": database,
            "database_ready": bool(probe.get("database_ready")),
            "canonical_indexes_ready": bool(probe.get("canonical_indexes_ready")),
            "credential_source": candidate.source,
            "credential_file_bound": True,
            "legacy_source_adopted": candidate.legacy,
            "candidate_count": len(candidates),
            "bootstrap_scope": ZERO_TOUCH_BOOTSTRAP_SCOPE,
            "canonical_domain_mutations": 0,
            "rule": "LEGACY_CREDENTIALS_ARE_ADOPTED_BEFORE_STALE_BINDINGS_ARE_REMOVED",
        }

    # Preserve compatibility with an explicitly unauthenticated local development
    # MongoDB, but prove it rather than silently assuming loopback is usable.
    try:
        probe = _probe_uri("mongodb://127.0.0.1:27017", database)
    except ZeroTouchBootstrapError as exc:
        if exc.code == "MONGODB_UNREACHABLE":
            raise
        if "BOOTSTRAP_AUTHORITY_REQUIRED" in failures or exc.code == "BOOTSTRAP_AUTHORITY_REQUIRED":
            raise ZeroTouchBootstrapError(
                "BOOTSTRAP_AUTHORITY_REQUIRED",
                "MongoDB requires authentication, but zero-touch setup found no reusable credential with authority on the canonical MangoMe database",
            ) from exc
        raise

    os.environ.pop("MANGOME_MONGODB_URI", None)
    os.environ.pop("MANGOME_MONGODB_URI_FILE", None)
    return {
        "status": "READY",
        "database": database,
        "database_ready": bool(probe.get("database_ready")),
        "canonical_indexes_ready": bool(probe.get("canonical_indexes_ready")),
        "credential_source": "UNAUTHENTICATED_LOOPBACK",
        "credential_file_bound": False,
        "legacy_source_adopted": False,
        "candidate_count": len(candidates),
        "bootstrap_scope": ZERO_TOUCH_BOOTSTRAP_SCOPE,
        "canonical_domain_mutations": 0,
        "rule": "UNAUTHENTICATED_LOOPBACK_IS_ACCEPTED_ONLY_AFTER_SUCCESSFUL_CANONICAL_BOOTSTRAP",
    }
