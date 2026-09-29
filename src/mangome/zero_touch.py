from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import stat
import subprocess
import time
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from .storage.mongo import MongoStore


ZERO_TOUCH_BOOTSTRAP_SCOPE = "CREDENTIAL_ADOPTION_AND_DECLARED_INDEX_BOOTSTRAP_ONLY"

_MANGOME_COLLECTION_MARKERS = {
    "requests", "projects", "families", "contracts", "specs", "slices", "plans",
    "claims", "evidence", "artifacts", "edges", "approvals", "project_views",
    "work_identities", "normative_baselines", "effects", "truth_assertions",
}


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
    database: str | None = None


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _looks_like_mongodb_uri(value: str) -> bool:
    text = str(value or "").strip()
    return text.startswith("mongodb://") or text.startswith("mongodb+srv://")


def _database_from_env(env: dict[str, Any]) -> str | None:
    value = str(env.get("MANGOME_DATABASE") or env.get("MANGOME_EXPECTED_DATABASE") or "").strip()
    return value or None


def _candidate_from_env(source: str, env: dict[str, Any], *, legacy: bool) -> list[_CredentialCandidate]:
    out: list[_CredentialCandidate] = []
    file_value = str(env.get("MANGOME_MONGODB_URI_FILE") or "").strip()
    uri_value = str(env.get("MANGOME_MONGODB_URI") or "").strip()
    database = _database_from_env(env)
    if file_value:
        out.append(_CredentialCandidate(source=f"{source}:FILE", kind="FILE", value=file_value, legacy=legacy, database=database))
    if _looks_like_mongodb_uri(uri_value):
        out.append(_CredentialCandidate(source=f"{source}:URI", kind="URI", value=uri_value, legacy=legacy, database=database))
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
            out.extend(_candidate_from_env(
                f"CODEX_CONFIG:{name}", env,
                legacy=legacy or str(name).lower() != "mangome",
            ))
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
                    f"{source}:{name}", env,
                    legacy=legacy or str(name).lower() != "mangome",
                ))

    collect(data.get("mcpServers"), "CLAUDE_CONFIG")
    projects = data.get("projects") or {}
    if isinstance(projects, dict):
        for project, project_data in projects.items():
            if isinstance(project_data, dict):
                collect(project_data.get("mcpServers"), f"CLAUDE_PROJECT:{project}")
    return out


def _live_process_environments(proc_root: Path = Path("/proc")) -> list[dict[str, str]]:
    """Return only MangoMe-related deployment variables from likely agent/MCP processes."""
    out: list[dict[str, str]] = []
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return out
    allowed = {
        b"MANGOME_MONGODB_URI", b"MANGOME_MONGODB_URI_FILE",
        b"MANGOME_DATABASE", b"MANGOME_EXPECTED_DATABASE",
    }
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").lower()
        except OSError:
            continue
        if not any(token in cmdline for token in (
            "mangome", "mcp_server", "worker_mcp_server", "mangome-mcp",
            "mangome_eval", "codex", "claude",
        )):
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
            if key in allowed:
                env[key.decode("ascii")] = value.decode("utf-8", "replace")
        if env:
            out.append(env)
    return out


def _live_process_candidates(proc_root: Path = Path("/proc")) -> list[_CredentialCandidate]:
    out: list[_CredentialCandidate] = []
    for env in _live_process_environments(proc_root):
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
    os.chmod(directory, 0o700)
    target = directory / "mongodb-uri"
    if target.is_symlink():
        raise ZeroTouchBootstrapError("CREDENTIAL_TARGET_UNSAFE", "managed MongoDB credential target must not be a symlink")
    temp = directory / ".mongodb-uri.tmp"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
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


def _managed_binding_path(home: Path) -> Path:
    return home / ".config" / "mangome" / "database-binding.json"


def _read_managed_database_binding(home: Path) -> dict[str, Any] | None:
    path = _managed_binding_path(home)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    database = str(data.get("database") or "").strip()
    if not database:
        return None
    return {
        "database": database,
        "adopted_existing": bool(data.get("adopted_existing")),
        "source": str(data.get("source") or "MANAGED_DATABASE_BINDING"),
    }


def _secure_managed_database_binding(home: Path, *, database: str, source: str, adopted_existing: bool) -> Path:
    database = str(database or "").strip()
    if not database:
        raise ZeroTouchBootstrapError("DATABASE_IDENTITY_INVALID", "database identity is empty")
    directory = home / ".config" / "mangome"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    target = _managed_binding_path(home)
    if target.is_symlink():
        raise ZeroTouchBootstrapError("DATABASE_BINDING_TARGET_UNSAFE", "managed database binding target must not be a symlink")
    temp = directory / ".database-binding.json.tmp"
    payload = {
        "protocol": "MDB/1",
        "database": database,
        "adopted_existing": bool(adopted_existing),
        "source": source,
        "rule": "DATABASE_IDENTITY_IS_PRESERVED_ACROSS_UPGRADES_UNLESS_EXPLICITLY_MIGRATED",
    }
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.chmod(temp, 0o600)
        os.replace(temp, target)
        os.chmod(target, 0o600)
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise ZeroTouchBootstrapError("DATABASE_BINDING_TARGET_UNWRITABLE", "cannot persist managed database identity") from exc
    return target.resolve()


def _classify_mongo_failure(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    name = type(exc).__name__
    if code in {13, 18} or name in {"AuthenticationFailure"}:
        return "AUTH"
    if name in {"ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect", "NetworkTimeout"}:
        return "UNREACHABLE"
    return "OTHER"


def _probe_uri(uri: str, database: str, *, require_existing_state: bool = False) -> dict[str, Any]:
    """Verify the exact database capability MangoMe needs, without domain writes."""
    store: MongoStore | None = None
    try:
        store = MongoStore(uri, database)
        store.db.command("ping")
        existing_markers: list[str] = []
        if require_existing_state:
            names = set(store.db.list_collection_names())
            existing_markers = sorted(names & _MANGOME_COLLECTION_MARKERS)
            if not existing_markers:
                raise ZeroTouchBootstrapError(
                    "LEGACY_DATABASE_NOT_ESTABLISHED",
                    "candidate database has no pre-existing MangoMe collections; implicit adoption is refused",
                )
        store.ensure_indexes()
        return {
            "database_ready": True,
            "canonical_indexes_ready": True,
            "existing_state_proven": bool(existing_markers) if require_existing_state else None,
            "existing_state_markers": existing_markers[:8],
        }
    except ZeroTouchBootstrapError:
        raise
    except Exception as exc:
        kind = _classify_mongo_failure(exc)
        if kind == "AUTH":
            raise ZeroTouchBootstrapError(
                "BOOTSTRAP_AUTHORITY_REQUIRED",
                "MongoDB authentication is required and the current credential does not authorize this MangoMe database",
            ) from exc
        if kind == "UNREACHABLE":
            raise ZeroTouchBootstrapError("MONGODB_UNREACHABLE", "MongoDB is unreachable from MangoMe") from exc
        raise ZeroTouchBootstrapError(
            "DATABASE_BOOTSTRAP_FAILED",
            f"MangoMe database bootstrap failed ({type(exc).__name__})",
        ) from exc
    finally:
        if store is not None:
            try:
                store.client.close()
            except Exception:
                pass


def _dedupe(candidates: Iterable[_CredentialCandidate]) -> list[_CredentialCandidate]:
    out: list[_CredentialCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        key = (item.kind, item.value, item.database or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _config_paths(workspace: Path, home: Path) -> list[tuple[Path, str, bool]]:
    return [
        (home / ".codex" / "config.toml", "codex", False),
        (workspace / ".codex" / "config.toml", "codex", False),
        (home / ".claude.json", "claude", False),
        (workspace / ".mcp.json", "claude", False),
        (home / ".codex" / "config.toml.mangome.bak", "codex", True),
        (workspace / ".codex" / "config.toml.mangome.bak", "codex", True),
        (home / ".claude.json.mangome.bak", "claude", True),
        (workspace / ".mcp.json.mangome.bak", "claude", True),
    ]


def _launcher_roots(workspace: Path, home: Path) -> list[Path]:
    """Return bounded local deployment roots that may hold the pre-v0.3.12 launcher.

    Launcher state is deployment state, not arbitrary filesystem discovery.  The
    search is intentionally limited to known MangoMe/eval locations and never
    traverses the whole home or host filesystem.
    """
    roots: list[Path] = []

    def add(path: Path) -> None:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            return
        if resolved not in roots:
            roots.append(resolved)

    source = os.environ.get("MANGOME_EXPECTED_SOURCE_ROOT", "").strip()
    if source:
        add(Path(source) / "eval")
        add(Path(source) / "launcher")
        add(Path(source) / "launchers")
    add(Path(__file__).resolve().parents[2] / "eval")
    add(workspace / "eval")
    add(workspace / "launcher")
    add(home / "MangoMe-latest" / "eval")
    add(home / ".config" / "mangome")
    return roots


def _parse_launcher_binding(path: Path) -> list[_CredentialCandidate]:
    """Parse a legacy launcher without executing or sourcing it.

    Only the four MangoMe MongoDB binding variables are recognized.  A launcher
    candidate is emitted only when credential source *and* database identity are
    present in the same file, preserving the historical binding atomically.
    """
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_size > 131072:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    wanted = {
        "MANGOME_MONGODB_URI", "MANGOME_MONGODB_URI_FILE",
        "MANGOME_DATABASE", "MANGOME_EXPECTED_DATABASE",
    }
    env: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in wanted:
            continue
        value = value.strip().rstrip(";").strip().strip("\"'")
        if value:
            env[key] = value

    database = _database_from_env(env)
    if not database:
        return []
    file_value = env.get("MANGOME_MONGODB_URI_FILE", "").strip()
    if file_value:
        credential_path = Path(file_value).expanduser()
        if not credential_path.is_absolute():
            credential_path = (path.parent / credential_path).resolve()
        env["MANGOME_MONGODB_URI_FILE"] = str(credential_path)
    candidates = _candidate_from_env(f"LOCAL_LAUNCHER:{path}", env, legacy=True)
    return [item for item in candidates if item.database == database]


def _launcher_candidates(workspace: Path, home: Path) -> list[_CredentialCandidate]:
    out: list[_CredentialCandidate] = []
    seen_files: set[Path] = set()
    for root in _launcher_roots(workspace, home):
        if not root.exists():
            continue
        if root.is_file():
            paths = [root]
        else:
            try:
                paths = [p for p in root.rglob("*") if p.is_file()]
            except OSError:
                continue
        for path in paths[:128]:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            out.extend(_parse_launcher_binding(resolved))
    return _dedupe(out)


def _collect_candidates(workspace: Path, home: Path) -> list[_CredentialCandidate]:
    candidates: list[_CredentialCandidate] = []
    env = {
        "MANGOME_MONGODB_URI_FILE": os.environ.get("MANGOME_MONGODB_URI_FILE", ""),
        "MANGOME_MONGODB_URI": os.environ.get("MANGOME_MONGODB_URI", ""),
        "MANGOME_DATABASE": os.environ.get("MANGOME_DATABASE", ""),
        "MANGOME_EXPECTED_DATABASE": os.environ.get("MANGOME_EXPECTED_DATABASE", ""),
    }
    candidates.extend(_candidate_from_env("PROCESS_ENVIRONMENT", env, legacy=False))

    managed_binding = _read_managed_database_binding(home)
    managed = home / ".config" / "mangome" / "mongodb-uri"
    if managed.is_file():
        candidates.append(_CredentialCandidate(
            "MANAGED_CREDENTIAL_FILE", "FILE", str(managed), False,
            database=(managed_binding or {}).get("database"),
        ))

    candidates.extend(_live_process_candidates())

    # Historical launchers can be the only durable place where credential source
    # and database identity still coexist.  Keep the pair together and inspect it
    # before stale client backups or the fresh-install default are considered.
    candidates.extend(_launcher_candidates(workspace, home))

    for path, kind, legacy in _config_paths(workspace, home):
        if kind == "codex":
            candidates.extend(_codex_candidates(path, legacy=legacy))
        else:
            candidates.extend(_claude_candidates(path, legacy=legacy))

    return _dedupe(candidates)


def _collect_database_hints(workspace: Path, home: Path) -> list[str]:
    """Recover database names independently of credentials."""
    hints: list[str] = []

    def add(value: Any) -> None:
        name = str(value or "").strip()
        if name and name not in hints:
            hints.append(name)

    add(os.environ.get("MANGOME_DATABASE"))
    add(os.environ.get("MANGOME_EXPECTED_DATABASE"))
    binding = _read_managed_database_binding(home)
    if binding:
        add(binding.get("database"))
    for env in _live_process_environments():
        add(env.get("MANGOME_DATABASE"))
        add(env.get("MANGOME_EXPECTED_DATABASE"))

    for path, kind, _legacy in _config_paths(workspace, home):
        if not path.is_file():
            continue
        try:
            if kind == "codex":
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                servers = data.get("mcp_servers") or {}
                if isinstance(servers, dict):
                    for name, entry in servers.items():
                        if str(name).lower().startswith("mangome") and isinstance(entry, dict):
                            env = entry.get("env") or {}
                            if isinstance(env, dict):
                                add(env.get("MANGOME_DATABASE"))
                                add(env.get("MANGOME_EXPECTED_DATABASE"))
            else:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    stacks = [data.get("mcpServers")]
                    projects = data.get("projects") or {}
                    if isinstance(projects, dict):
                        stacks.extend(v.get("mcpServers") for v in projects.values() if isinstance(v, dict))
                    for servers in stacks:
                        if not isinstance(servers, dict):
                            continue
                        for name, entry in servers.items():
                            if str(name).lower().startswith("mangome") and isinstance(entry, dict):
                                env = entry.get("env") or {}
                                if isinstance(env, dict):
                                    add(env.get("MANGOME_DATABASE"))
                                    add(env.get("MANGOME_EXPECTED_DATABASE"))
        except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            continue
    return hints


def _local_root_provision_enabled() -> bool:
    override = os.environ.get("MANGOME_ZERO_TOUCH_LOCAL_PROVISION")
    if override is not None:
        return _truthy(override)
    return bool(
        hasattr(os, "geteuid")
        and os.geteuid() == 0
        and os.environ.get("MANGOME_DEPLOYMENT_ID", "").strip() == "managed-local"
    )


def _mongod_service_name() -> str:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        raise ZeroTouchBootstrapError("LOCAL_PROVISION_UNSUPPORTED", "systemctl is unavailable")
    for name in ("mongod.service", "mongodb.service"):
        probe = subprocess.run(
            [systemctl, "show", name, "--property=LoadState", "--value"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
        )
        if probe.returncode == 0 and probe.stdout.strip() == "loaded":
            return name
    raise ZeroTouchBootstrapError("LOCAL_PROVISION_UNSUPPORTED", "no supported local MongoDB systemd service was found")


def _mongod_config_path() -> Path:
    for value in ("/etc/mongod.conf", "/etc/mongodb.conf"):
        path = Path(value)
        if path.is_file():
            return path
    raise ZeroTouchBootstrapError("LOCAL_PROVISION_UNSUPPORTED", "MongoDB configuration file was not found")


def _parse_simple_mongod_config(path: Path) -> dict[str, str]:
    """Parse only scalar top-level/one-level YAML keys needed for safety checks."""
    out: dict[str, str] = {}
    section: str | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ZeroTouchBootstrapError("LOCAL_PROVISION_UNSUPPORTED", "MongoDB configuration is unreadable") from exc
    for raw in lines:
        without_comment = raw.split("#", 1)[0].rstrip()
        if not without_comment.strip():
            continue
        indent = len(without_comment) - len(without_comment.lstrip())
        stripped = without_comment.strip()
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1].strip()
            out[f"{section}.__present__"] = "1"
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key, value = key.strip(), value.strip().strip("'\"")
        if indent == 0:
            section = None
            out[key] = value
        elif section:
            out[f"{section}.{key}"] = value
    return out


def _assert_local_provision_safety(config: dict[str, str]) -> None:
    if str(config.get("security.authorization", "")).lower() != "enabled":
        raise ZeroTouchBootstrapError("LOCAL_PROVISION_NOT_REQUIRED", "MongoDB authorization is not enabled")
    bind = str(config.get("net.bindIp", "127.0.0.1")).replace(" ", "")
    allowed = {"127.0.0.1", "localhost", "::1"}
    if bind:
        hosts = {h for h in bind.split(",") if h}
        if not hosts or not hosts.issubset(allowed):
            raise ZeroTouchBootstrapError(
                "LOCAL_PROVISION_UNSAFE_ENDPOINT",
                "automatic local credential provisioning is allowed only for loopback-only MongoDB",
            )
    if _truthy(config.get("net.bindIpAll")):
        raise ZeroTouchBootstrapError("LOCAL_PROVISION_UNSAFE_ENDPOINT", "MongoDB bindIpAll prevents automatic local provisioning")
    if "replication.__present__" in config or "sharding.__present__" in config:
        raise ZeroTouchBootstrapError(
            "LOCAL_PROVISION_UNSUPPORTED_TOPOLOGY",
            "automatic local provisioning is disabled for replica-set or sharded MongoDB",
        )
    if config.get("security.keyFile") or config.get("security.clusterAuthMode"):
        raise ZeroTouchBootstrapError(
            "LOCAL_PROVISION_UNSUPPORTED_TOPOLOGY",
            "automatic local provisioning is disabled for keyFile/cluster-auth deployments",
        )


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _choose_existing_database(client: Any, requested_database: str, hints: list[str]) -> tuple[str, bool, list[str]]:
    observed: list[tuple[str, list[str]]] = []
    for name in client.list_database_names():
        if name in {"admin", "config", "local"}:
            continue
        try:
            markers = sorted(set(client[name].list_collection_names()) & _MANGOME_COLLECTION_MARKERS)
        except Exception:
            continue
        if markers:
            observed.append((name, markers))

    if not observed:
        return requested_database, False, []

    max_score = max(len(markers) for _, markers in observed)
    best = [(name, markers) for name, markers in observed if len(markers) == max_score]
    if len(best) == 1:
        return best[0][0], best[0][0] != requested_database, best[0][1]

    hinted = [(name, markers) for name, markers in best if name in hints]
    if len(hinted) == 1:
        return hinted[0][0], hinted[0][0] != requested_database, hinted[0][1]

    raise ZeroTouchBootstrapError(
        "DATABASE_IDENTITY_AMBIGUOUS",
        "multiple existing MangoMe databases were found; automatic upgrade refuses to guess the canonical database",
    )


def _provision_local_runtime_credential(
    workspace: Path,
    home: Path,
    requested_database: str,
) -> dict[str, Any]:
    """Root-only local recovery for a standalone loopback MongoDB.

    The normal authenticated mongod is stopped briefly. A temporary loopback-only
    no-auth process opens the same local data files, identifies the existing MangoMe
    database by collection markers, creates/rotates one database-scoped runtime user,
    shuts down, and restarts the normal authenticated service. No database is copied,
    renamed, dropped, or migrated.
    """
    if not _local_root_provision_enabled():
        raise ZeroTouchBootstrapError(
            "BOOTSTRAP_AUTHORITY_REQUIRED",
            "no reusable MongoDB credential exists and privileged local provisioning is not enabled",
        )

    service = _mongod_service_name()
    config_path = _mongod_config_path()
    config = _parse_simple_mongod_config(config_path)
    _assert_local_provision_safety(config)

    systemctl = shutil.which("systemctl")
    mongod = shutil.which("mongod") or ("/usr/bin/mongod" if Path("/usr/bin/mongod").is_file() else None)
    runuser = shutil.which("runuser")
    if not systemctl or not mongod or not runuser:
        raise ZeroTouchBootstrapError(
            "LOCAL_PROVISION_UNSUPPORTED",
            "required local MongoDB service-management tools are unavailable",
        )

    active = subprocess.run(
        [systemctl, "is-active", "--quiet", service],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
    ).returncode == 0
    if not active:
        raise ZeroTouchBootstrapError(
            "LOCAL_PROVISION_UNSUPPORTED",
            "automatic local provisioning requires the managed MongoDB service to be active",
        )

    user_result = subprocess.run(
        [systemctl, "show", service, "--property=User", "--value"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
    )
    service_user = user_result.stdout.strip() if user_result.returncode == 0 else ""
    if not service_user:
        service_user = "mongodb"

    hints = _collect_database_hints(workspace, home)
    temp_port = _free_loopback_port()
    temp_uri = f"mongodb://127.0.0.1:{temp_port}"
    temp_process: subprocess.Popen[Any] | None = None
    temp_store: MongoStore | None = None
    selected_database = requested_database
    adopted_existing = False
    existing_markers: list[str] = []
    password = secrets.token_urlsafe(36)
    username = "mangome_runtime"
    normal_service_restart_error: Exception | None = None

    subprocess.run(
        [systemctl, "stop", service],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=30,
    )

    try:
        env = dict(os.environ)
        env.pop("MONGODB_CONFIG_OVERRIDE_NOFORK", None)
        cmd = [
            runuser, "-u", service_user, "--",
            mongod, "--config", str(config_path),
            "--noauth",
            "--bind_ip", "127.0.0.1",
            "--port", str(temp_port),
            "--nounixsocket",
        ]
        temp_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        deadline = time.monotonic() + 20.0
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if temp_process.poll() is not None:
                raise ZeroTouchBootstrapError(
                    "LOCAL_PROVISION_TEMP_START_FAILED",
                    "temporary local MongoDB bootstrap process exited before becoming ready",
                )
            try:
                temp_store = MongoStore(temp_uri, "admin")
                temp_store.client.admin.command("ping")
                break
            except Exception as exc:
                last_error = exc
                if temp_store is not None:
                    try:
                        temp_store.client.close()
                    except Exception:
                        pass
                    temp_store = None
                time.sleep(0.25)
        else:
            raise ZeroTouchBootstrapError(
                "LOCAL_PROVISION_TEMP_START_FAILED",
                f"temporary local MongoDB bootstrap process did not become ready ({type(last_error).__name__ if last_error else 'timeout'})",
            )

        assert temp_store is not None
        selected_database, adopted_existing, existing_markers = _choose_existing_database(
            temp_store.client, requested_database, hints
        )
        db = temp_store.client[selected_database]
        roles = [{"role": "readWrite", "db": selected_database}]
        info = db.command({"usersInfo": username})
        if list(info.get("users") or []):
            db.command({"updateUser": username, "pwd": password, "roles": roles})
        else:
            db.command({"createUser": username, "pwd": password, "roles": roles})

        try:
            temp_store.client.admin.command({"shutdown": 1, "force": True})
        except Exception:
            # Successful shutdown normally closes the connection before a reply.
            pass
        try:
            temp_process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            temp_process.terminate()
            try:
                temp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                temp_process.kill()
                temp_process.wait(timeout=5)
        temp_process = None
    finally:
        if temp_store is not None:
            try:
                temp_store.client.close()
            except Exception:
                pass
        if temp_process is not None and temp_process.poll() is None:
            temp_process.terminate()
            try:
                temp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                temp_process.kill()
                temp_process.wait(timeout=5)
        try:
            subprocess.run(
                [systemctl, "start", service],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=30,
            )
        except Exception as exc:
            normal_service_restart_error = exc

    if normal_service_restart_error is not None:
        raise ZeroTouchBootstrapError(
            "LOCAL_PROVISION_RESTART_FAILED",
            "MongoDB runtime credential was provisioned but the normal authenticated service could not be restarted",
        ) from normal_service_restart_error

    encoded_user = quote(username, safe="")
    encoded_password = quote(password, safe="")
    encoded_db = quote(selected_database, safe="")
    uri = (
        f"mongodb://{encoded_user}:{encoded_password}@127.0.0.1:27017/"
        f"{encoded_db}?authSource={encoded_db}"
    )
    probe = _probe_uri(uri, selected_database, require_existing_state=adopted_existing)
    credential_path = _secure_managed_credential_file(home, uri)
    _secure_managed_database_binding(
        home,
        database=selected_database,
        source="LOCAL_ROOT_PROVISION",
        adopted_existing=adopted_existing,
    )

    os.environ["MANGOME_MONGODB_URI_FILE"] = str(credential_path)
    os.environ.pop("MANGOME_MONGODB_URI", None)
    os.environ["MANGOME_DATABASE"] = selected_database
    os.environ["MANGOME_EXPECTED_DATABASE"] = selected_database
    if adopted_existing:
        os.environ["MANGOME_ADOPT_EXISTING_DATABASE"] = "1"
    else:
        os.environ.pop("MANGOME_ADOPT_EXISTING_DATABASE", None)

    return {
        "status": "READY",
        "database": selected_database,
        "requested_database": requested_database,
        "database_ready": bool(probe.get("database_ready")),
        "canonical_indexes_ready": bool(probe.get("canonical_indexes_ready")),
        "credential_source": "LOCAL_ROOT_PROVISION",
        "credential_file_bound": True,
        "local_runtime_user_provisioned": True,
        "legacy_source_adopted": False,
        "existing_database_identity_adopted": adopted_existing,
        "database_migration_performed": False,
        "existing_state_markers": existing_markers[:8],
        "bootstrap_scope": ZERO_TOUCH_BOOTSTRAP_SCOPE,
        "canonical_domain_mutations": 0,
        "rule": "LOCAL_ROOT_PROVISION_PRESERVES_EXISTING_DATABASE_IDENTITY_AND_CREATES_DATABASE_SCOPED_RUNTIME_AUTHORITY",
    }


def prepare_mongodb_runtime(
    workspace_root: str | Path,
    *,
    database: str = "mangome",
    home: str | None = None,
) -> dict[str, Any]:
    """Zero-touch adoption/bootstrap for a managed MongoDB runtime.

    Order:
      1. Reuse an existing credential and its database identity.
      2. Reuse an explicitly unauthenticated local MongoDB.
      3. For root-owned managed-local standalone deployments only, recover locally by
         provisioning one database-scoped runtime user while preserving the existing
         MangoMe database identity.

    No database copy, rename, drop, or MangoMe schema migration occurs here.
    """
    workspace = Path(workspace_root).expanduser().resolve()
    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    requested_database = str(database or "mangome").strip() or "mangome"
    persisted = _read_managed_database_binding(home_path)
    candidates = _collect_candidates(workspace, home_path)
    failures: list[str] = []

    def database_attempts(candidate: _CredentialCandidate) -> list[str]:
        # Credential source and database identity form one deployment binding.
        # Never let a stale persisted default (for example a failed v0.3.12
        # ``mangome`` binding) override the database explicitly carried by a
        # discovered working launcher/legacy credential.
        persisted_database = str((persisted or {}).get("database") or "").strip()
        ordered: list[str] = []
        for value in (candidate.database, persisted_database, requested_database):
            name = str(value or "").strip()
            if name and name not in ordered:
                ordered.append(name)
        return ordered

    for candidate in candidates:
        try:
            uri = _read_uri_file(candidate.value) if candidate.kind == "FILE" else candidate.value.strip()
        except ZeroTouchBootstrapError as exc:
            failures.append(exc.code)
            continue

        for candidate_database in database_attempts(candidate):
            try:
                probe = _probe_uri(
                    uri,
                    candidate_database,
                    require_existing_state=(
                        candidate_database != requested_database
                        or bool(candidate.legacy)
                        or bool(persisted and candidate_database == persisted.get("database"))
                    ),
                )
            except ZeroTouchBootstrapError as exc:
                failures.append(exc.code)
                continue

            adopted_existing = candidate_database != requested_database or bool(candidate.legacy)
            target = _secure_managed_credential_file(home_path, uri)
            _secure_managed_database_binding(
                home_path,
                database=candidate_database,
                source=candidate.source,
                adopted_existing=adopted_existing,
            )
            os.environ["MANGOME_MONGODB_URI_FILE"] = str(target)
            os.environ.pop("MANGOME_MONGODB_URI", None)
            os.environ["MANGOME_DATABASE"] = candidate_database
            os.environ["MANGOME_EXPECTED_DATABASE"] = candidate_database
            if adopted_existing:
                os.environ["MANGOME_ADOPT_EXISTING_DATABASE"] = "1"
            else:
                os.environ.pop("MANGOME_ADOPT_EXISTING_DATABASE", None)
            return {
                "status": "READY",
                "database": candidate_database,
                "requested_database": requested_database,
                "database_ready": bool(probe.get("database_ready")),
                "canonical_indexes_ready": bool(probe.get("canonical_indexes_ready")),
                "credential_source": candidate.source,
                "credential_file_bound": True,
                "legacy_source_adopted": candidate.legacy,
                "existing_database_identity_adopted": adopted_existing,
                "database_migration_performed": False,
                "candidate_count": len(candidates),
                "bootstrap_scope": ZERO_TOUCH_BOOTSTRAP_SCOPE,
                "canonical_domain_mutations": 0,
                "rule": "EXISTING_DATABASE_IDENTITY_WINS_OVER_NEW_DEFAULT; NO_IMPLICIT_DATABASE_MIGRATION",
            }

    unauth_database = str((persisted or {}).get("database") or requested_database).strip() or requested_database
    try:
        probe = _probe_uri("mongodb://127.0.0.1:27017", unauth_database)
    except ZeroTouchBootstrapError as exc:
        if exc.code == "MONGODB_UNREACHABLE":
            raise
        if exc.code != "BOOTSTRAP_AUTHORITY_REQUIRED" and "BOOTSTRAP_AUTHORITY_REQUIRED" not in failures:
            raise
    else:
        _secure_managed_database_binding(
            home_path,
            database=unauth_database,
            source="UNAUTHENTICATED_LOOPBACK",
            adopted_existing=unauth_database != requested_database,
        )
        os.environ.pop("MANGOME_MONGODB_URI", None)
        os.environ.pop("MANGOME_MONGODB_URI_FILE", None)
        os.environ["MANGOME_DATABASE"] = unauth_database
        os.environ["MANGOME_EXPECTED_DATABASE"] = unauth_database
        if unauth_database != requested_database:
            os.environ["MANGOME_ADOPT_EXISTING_DATABASE"] = "1"
        else:
            os.environ.pop("MANGOME_ADOPT_EXISTING_DATABASE", None)
        return {
            "status": "READY",
            "database": unauth_database,
            "requested_database": requested_database,
            "database_ready": bool(probe.get("database_ready")),
            "canonical_indexes_ready": bool(probe.get("canonical_indexes_ready")),
            "credential_source": "UNAUTHENTICATED_LOOPBACK",
            "credential_file_bound": False,
            "legacy_source_adopted": False,
            "existing_database_identity_adopted": unauth_database != requested_database,
            "database_migration_performed": False,
            "candidate_count": len(candidates),
            "bootstrap_scope": ZERO_TOUCH_BOOTSTRAP_SCOPE,
            "canonical_domain_mutations": 0,
            "rule": "UNAUTHENTICATED_LOOPBACK_ACCEPTED_ONLY_AFTER_SUCCESSFUL_CANONICAL_BOOTSTRAP",
        }

    # Final managed-local fallback: the user must not be asked to hand-create a
    # MongoDB user or credential file on a root-owned single-host installation.
    return _provision_local_runtime_credential(
        workspace,
        home_path,
        requested_database,
    )
