from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .operability import OperabilityError
from .storage.mongo import MongoStore
from .trust_boundary import enforce_mongo_role_boundary, resolve_mongodb_connection

ZERO_TOUCH_BOOTSTRAP_SCOPE = "LOCAL_HOST_AUTO_MIGRATION_AND_READINESS"
CANONICAL_DATABASE = "mangome"
LEGACY_DATABASES = {"mangome_uai_eval"}

_LEGACY_ENV_KEYS = (
    "MANGOME_MONGODB_URI_FILE",
    "MANGOME_MONGODB_URI",
    "MANGOME_ADOPT_EXISTING_DATABASE",
    "MANGOME_ZERO_TOUCH_LOCAL_PROVISION",
)
_LEGACY_FILES = (
    ".config/mangome/mongodb-uri",
    ".config/mangome/mongodb-maintenance-uri",
    ".config/mangome/database-binding.json",
)


class ZeroTouchBootstrapError(RuntimeError):
    """Fail-closed local-host bootstrap error with a stable operator-facing code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def _legacy_candidate_loopback_uri(home: str | None = None) -> str:
    """Derive only endpoint coordinates from stale local MangoMe bindings.

    Credential material is never returned or logged. v0.3.17 supports the canonical
    local endpoint on port 27017; anything else fails closed instead of silently
    changing deployment identity.
    """

    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    candidates: list[str] = []
    raw = os.environ.get("MANGOME_MONGODB_URI", "").strip()
    if raw:
        candidates.append(raw)
    uri_file = os.environ.get("MANGOME_MONGODB_URI_FILE", "").strip()
    file_candidates: list[Path] = []
    if uri_file:
        file_candidates.append(Path(uri_file).expanduser())
    file_candidates.append(home_path / ".config/mangome/mongodb-uri")
    for path in file_candidates:
        try:
            if path.is_file():
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    candidates.append(value)
        except OSError:
            continue

    uri = candidates[0] if candidates else "mongodb://127.0.0.1:27017"
    parsed = urlparse(uri)
    host = parsed.hostname or ""
    port = int(parsed.port or 27017)
    if parsed.scheme != "mongodb" or host not in {"127.0.0.1", "localhost", "::1"}:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_ENDPOINT_REQUIRED",
            "legacy MangoMe binding is not a loopback MongoDB endpoint; zero-touch cleanup stopped before deleting credentials",
        )
    if port != 27017:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_NONSTANDARD_PORT_REQUIRES_EXPLICIT_CONFIG",
            "v0.3.16 zero-touch cleanup will not discard a legacy non-standard MongoDB port binding",
        )
    return "mongodb://127.0.0.1:27017"


def _cleanup_legacy_local_host_state(home: str | None = None) -> dict[str, Any]:
    """Remove only obsolete MangoMe credential/binding residue for LOCAL_HOST."""

    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    removed_files: list[str] = []
    cleared_env: list[str] = []

    for rel in _LEGACY_FILES:
        path = home_path / rel
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
                removed_files.append(str(path))
        except OSError as exc:
            raise ZeroTouchBootstrapError(
                "LOCAL_HOST_LEGACY_CLEANUP_FAILED",
                f"could not remove obsolete MangoMe runtime artifact {path}",
            ) from exc

    for key in _LEGACY_ENV_KEYS:
        if key in os.environ:
            os.environ.pop(key, None)
            cleared_env.append(key)

    os.environ["MANGOME_TRUST_BOUNDARY"] = "LOCAL_HOST"
    os.environ["MANGOME_DATABASE"] = CANONICAL_DATABASE
    os.environ["MANGOME_EXPECTED_DATABASE"] = CANONICAL_DATABASE
    os.environ["MANGOME_ALLOW_EVAL_DATABASE"] = "0"
    os.environ["MANGOME_ZERO_TOUCH_BOOTSTRAP"] = "1"

    return {
        "removed_files": removed_files,
        "cleared_environment_keys": cleared_env,
        "credential_residue_remaining": False,
    }


def _uri_port(uri: str) -> int:
    parsed = urlparse(uri)
    if parsed.scheme != "mongodb":
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_ENDPOINT_REQUIRED",
            "LOCAL_HOST requires a mongodb:// loopback URI",
        )
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_ENDPOINT_REQUIRED",
            "LOCAL_HOST host migration is allowed only for a loopback MongoDB endpoint",
        )
    return int(parsed.port or 27017)


def _loopback_listener_snapshot(port: int) -> dict[str, Any]:
    ss = shutil.which("ss")
    if not ss:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_LISTENER_PROOF_UNAVAILABLE",
            "cannot prove MongoDB listener scope because the ss utility is unavailable",
        )
    try:
        proc = subprocess.run(
            [ss, "-H", "-ltn"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_LISTENER_PROOF_UNAVAILABLE",
            "cannot inspect the active MongoDB listener",
        ) from exc
    if proc.returncode != 0:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_LISTENER_PROOF_UNAVAILABLE",
            "cannot inspect the active MongoDB listener",
        )

    endpoints: list[str] = []
    unsafe: list[str] = []
    suffix = f":{port}"
    for raw in proc.stdout.splitlines():
        fields = raw.split()
        if len(fields) < 4:
            continue
        local = fields[3]
        if not local.endswith(suffix):
            continue
        endpoints.append(local)
        if local.startswith("[") and "]" in local:
            host = local[1 : local.index("]")]
        else:
            host = local.rsplit(":", 1)[0]
        host = host.strip()
        if host not in {"127.0.0.1", "::1", "localhost"}:
            unsafe.append(local)

    if not endpoints:
        raise ZeroTouchBootstrapError(
            "MONGODB_UNREACHABLE",
            f"no active MongoDB TCP listener was found on port {port}",
        )
    if unsafe:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_NON_LOOPBACK_LISTENER",
            "MongoDB has a non-loopback listener; authorization will not be disabled",
        )
    return {"port": port, "endpoints": endpoints, "scope": "LOOPBACK"}


def _systemctl(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_SERVICE_MANAGER_UNAVAILABLE",
            "systemctl is required for managed LOCAL_HOST MongoDB migration",
        )
    try:
        return subprocess.run(
            [systemctl, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_SERVICE_MANAGER_UNAVAILABLE",
            "could not invoke systemctl for mongod.service",
        ) from exc


def _main_pid(service: str) -> int | None:
    proc = _systemctl("show", service, "--property=MainPID", "--value", timeout=5)
    if proc.returncode != 0:
        return None
    try:
        pid = int(proc.stdout.strip() or "0")
    except ValueError:
        return None
    return pid or None


def _active_cmdline(service: str) -> list[str]:
    pid = _main_pid(service)
    if not pid:
        return []
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _rewrite_mongod_config(text: str) -> tuple[str, bool, str]:
    """Prepare LOCAL_HOST access without breaking MongoDB member authentication.

    Two supported configurations exist:

    * no ``security.keyFile``: disable client authorization directly;
    * ``security.keyFile`` present: preserve the key file and internal member
      authentication, and enable ``security.transitionToAuth: true`` so local
      unauthenticated clients are accepted while the deployment stays loopback-only.

    ``clusterAuthMode`` is preserved when a keyFile exists. X.509/cluster-only
    security without a keyFile remains fail-closed because MangoMe cannot prove a
    safe automatic transition for that deployment.
    """

    lines = text.splitlines(keepends=True)
    top_security = [
        idx
        for idx, line in enumerate(lines)
        if line == line.lstrip(" ") and line.lstrip().startswith("security:")
    ]
    security_indexes = [
        idx
        for idx in top_security
        if re.match(r"^security\s*:\s*(?:#.*)?(?:\r?\n)?$", lines[idx])
    ]
    if top_security and len(security_indexes) != len(top_security):
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_MONGOD_CONFIG_AMBIGUOUS",
            "inline/complex top-level security configuration is not safe for automatic rewrite",
        )
    if len(security_indexes) > 1:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_MONGOD_CONFIG_AMBIGUOUS",
            "multiple top-level security sections found in mongod.conf",
        )

    if not security_indexes:
        suffix = "" if not text or text.endswith("\n") else "\n"
        return text + suffix + "security:\n  authorization: disabled\n", True, "AUTHORIZATION_DISABLED"

    start = security_indexes[0]
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(lines[idx]) - len(lines[idx].lstrip(" "))
        if indent == 0:
            end = idx
            break

    key_indexes: dict[str, list[int]] = {}
    for idx in range(start + 1, end):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key = stripped.split(":", 1)[0].strip()
        key_indexes.setdefault(key, []).append(idx)

    for key in ("authorization", "keyFile", "clusterAuthMode", "transitionToAuth"):
        if len(key_indexes.get(key, [])) > 1:
            raise ZeroTouchBootstrapError(
                "LOCAL_HOST_MONGOD_CONFIG_AMBIGUOUS",
                f"multiple security.{key} entries found in mongod.conf",
            )

    keyfile_idx = (key_indexes.get("keyFile") or [None])[0]
    transition_idx = (key_indexes.get("transitionToAuth") or [None])[0]
    cluster_mode_idx = (key_indexes.get("clusterAuthMode") or [None])[0]
    auth_idx = (key_indexes.get("authorization") or [None])[0]

    # MongoDB documents transitionToAuth as the rolling state in which a process
    # with an internal authentication mechanism such as keyFile accepts both
    # authenticated and unauthenticated connections and does not enforce user access
    # control. Keep the keyFile untouched: it may be required for replica-set/member
    # authentication even though local client RBAC is intentionally not enforced.
    if keyfile_idx is not None:
        if transition_idx is None:
            indent = lines[keyfile_idx][: len(lines[keyfile_idx]) - len(lines[keyfile_idx].lstrip(" "))]
            newline = "\r\n" if lines[keyfile_idx].endswith("\r\n") else "\n"
            lines.insert(keyfile_idx + 1, f"{indent}transitionToAuth: true{newline}")
            return "".join(lines), True, "KEYFILE_TRANSITION_TO_AUTH"

        original = lines[transition_idx]
        indent = original[: len(original) - len(original.lstrip(" "))]
        comment = ""
        if "#" in original:
            raw_comment = original.split("#", 1)[1].rstrip("\r\n")
            comment = f" # {raw_comment.strip()}" if raw_comment.strip() else ""
        newline = "\r\n" if original.endswith("\r\n") else "\n"
        replacement = f"{indent}transitionToAuth: true{comment}{newline}"
        if original == replacement:
            return text, False, "KEYFILE_TRANSITION_TO_AUTH"
        lines[transition_idx] = replacement
        return "".join(lines), True, "KEYFILE_TRANSITION_TO_AUTH"

    # A cluster security mode without keyFile may rely on X.509 or another internal
    # mechanism. Do not guess at that topology in a zero-touch host rewrite.
    if cluster_mode_idx is not None or transition_idx is not None:
        key = "clusterAuthMode" if cluster_mode_idx is not None else "transitionToAuth"
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_COMPLEX_MONGODB_SECURITY_CONFIGURATION",
            f"security.{key} is configured without security.keyFile; automatic LOCAL_HOST migration stopped",
        )

    if auth_idx is not None:
        original = lines[auth_idx]
        indent = original[: len(original) - len(original.lstrip(" "))]
        comment = ""
        if "#" in original:
            raw_comment = original.split("#", 1)[1].rstrip("\r\n")
            comment = f" # {raw_comment.strip()}" if raw_comment.strip() else ""
        newline = "\r\n" if original.endswith("\r\n") else "\n"
        replacement = f"{indent}authorization: disabled{comment}{newline}"
        if original == replacement:
            return text, False, "AUTHORIZATION_DISABLED"
        lines[auth_idx] = replacement
        return "".join(lines), True, "AUTHORIZATION_DISABLED"

    insert = "  authorization: disabled\n"
    lines.insert(start + 1, insert)
    return "".join(lines), True, "AUTHORIZATION_DISABLED"

def _atomic_replace_config(path: Path, content: str) -> None:
    stat = path.stat()
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".mangome-", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, stat.st_mode & 0o7777)
        try:
            os.chown(tmp, stat.st_uid, stat.st_gid)
        except PermissionError:
            pass
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _mongod_config_path(cmdline: list[str]) -> Path:
    configured = os.environ.get("MANGOME_MONGOD_CONFIG", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    for idx, arg in enumerate(cmdline):
        if arg.startswith("--config="):
            return Path(arg.split("=", 1)[1]).expanduser().resolve()
        if arg in {"--config", "-f"} and idx + 1 < len(cmdline):
            return Path(cmdline[idx + 1]).expanduser().resolve()
    return Path("/etc/mongod.conf").resolve()


def _migrate_local_host_authorization(uri: str) -> dict[str, Any]:
    """Perform the supported v0.3.17 LOCAL_HOST host migration, fail-closed."""

    if not _truthy_env("MANGOME_ZERO_TOUCH_HOST_MIGRATION", default=True):
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_HOST_MIGRATION_DISABLED",
            "MongoDB authorization is enabled and automatic LOCAL_HOST host migration is disabled",
        )
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_HOST_MIGRATION_REQUIRES_ROOT",
            "MongoDB authorization is enabled; zero-touch LOCAL_HOST migration requires root on this host",
        )

    port = _uri_port(uri)
    listener_before = _loopback_listener_snapshot(port)
    service = os.environ.get("MANGOME_MONGOD_SERVICE", "mongod.service").strip() or "mongod.service"
    active = _systemctl("is-active", "--quiet", service, timeout=5)
    if active.returncode != 0:
        raise ZeroTouchBootstrapError(
            "MONGODB_SERVICE_NOT_ACTIVE",
            f"{service} is not active",
        )

    cmdline = _active_cmdline(service)
    if any(arg == "--auth" or arg.startswith("--auth=") for arg in cmdline):
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_COMMAND_LINE_AUTH_UNSUPPORTED",
            "mongod authorization is forced by process arguments; MangoMe will not rewrite the service command line",
        )
    if any(arg in {"--keyFile", "--clusterAuthMode"} or arg.startswith("--keyFile=") or arg.startswith("--clusterAuthMode=") for arg in cmdline):
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_COMMAND_LINE_CLUSTER_SECURITY_UNSUPPORTED",
            "mongod cluster/key-file security is forced by process arguments; zero-touch cannot safely persist transitionToAuth in that service command line",
        )

    config_path = _mongod_config_path(cmdline)
    if not config_path.is_file():
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_MONGOD_CONFIG_NOT_FOUND",
            f"active LOCAL_HOST migration requires {config_path}",
        )

    original = config_path.read_text(encoding="utf-8")
    updated, changed, security_strategy = _rewrite_mongod_config(original)
    backup_path: Path | None = None

    if changed:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = config_path.with_name(f"{config_path.name}.mangome-v0.3.17-{stamp}.bak")
        shutil.copy2(config_path, backup_path)
        _atomic_replace_config(config_path, updated)

    restart = _systemctl("restart", service, timeout=30)
    if restart.returncode != 0:
        if changed and backup_path is not None and backup_path.is_file():
            try:
                shutil.copy2(backup_path, config_path)
                _systemctl("restart", service, timeout=30)
            except Exception:
                pass
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_MONGODB_RESTART_FAILED",
            f"{service} failed to restart after LOCAL_HOST migration",
        )

    deadline = time.monotonic() + 15.0
    listener_after: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if _systemctl("is-active", "--quiet", service, timeout=5).returncode == 0:
            try:
                listener_after = _loopback_listener_snapshot(port)
                break
            except ZeroTouchBootstrapError:
                pass
        time.sleep(0.5)
    if listener_after is None:
        raise ZeroTouchBootstrapError(
            "LOCAL_HOST_MONGODB_POST_RESTART_VERIFY_FAILED",
            "mongod.service did not return as a verified loopback-only listener",
        )

    return {
        "performed": True,
        "service": service,
        "config_path": str(config_path),
        "backup_path": str(backup_path) if backup_path else None,
        "config_changed": changed,
        "listener_before": listener_before,
        "listener_after": listener_after,
        "authorization": "not_enforced",
        "security_strategy": security_strategy,
        "restart_count": 1,
    }


def _probe_ready(uri: str) -> None:
    store = MongoStore(uri, CANONICAL_DATABASE)
    try:
        store.db.command("ping")
        enforce_mongo_role_boundary(store)
        store.ensure_indexes()
    finally:
        try:
            store.client.close()
        except Exception:
            pass


def prepare_mongodb_runtime(
    workspace_root: str | Path,
    *,
    database: str = CANONICAL_DATABASE,
    home: str | None = None,
) -> dict[str, Any]:
    """Make the managed single-host MongoDB runtime ready without user intervention.

    v0.3.17 LOCAL_HOST is intentionally credential-free. Zero-touch proves the
    loopback boundary before changing host security posture. If the existing local
    mongod still enforces authorization, a root-managed runtime performs one bounded
    migration: plain authorization is disabled directly; when security.keyFile is
    present, the keyFile is preserved and security.transitionToAuth is enabled so
    local client access is unauthenticated without breaking member authentication.
    mongod.service is restarted once and readiness is proved before legacy MangoMe
    credential/binding residue is deleted.

    No database is adopted or migrated. Legacy databases remain fail-closed.
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
            f"managed MangoMe v0.3.17 requires database {CANONICAL_DATABASE!r}, got {requested_database!r}",
        )

    cleanup: dict[str, Any] = {
        "removed_files": [],
        "cleared_environment_keys": [],
        "credential_residue_remaining": True,
    }
    host_migration: dict[str, Any] = {"performed": False}

    try:
        # Derive only the endpoint from any stale credential-era binding. Do not
        # delete credentials until the replacement credential-free LOCAL_HOST path
        # has been proven ready; failed migration must not destroy the old recovery path.
        candidate_uri = _legacy_candidate_loopback_uri(home)
        try:
            _probe_ready(candidate_uri)
        except Exception as exc:
            mapped = _map_failure(exc)
            if mapped.code != "LOCAL_HOST_MONGODB_AUTHORIZATION_ENABLED":
                raise mapped from exc
            host_migration = _migrate_local_host_authorization(candidate_uri)
            _probe_ready(candidate_uri)

        # Only after the no-auth loopback path works do we delete v0.3.12/v0.3.13
        # MangoMe credential/binding residue and switch the process to clean LOCAL_HOST.
        cleanup = _cleanup_legacy_local_host_state(home)
        config = resolve_mongodb_connection()
        _probe_ready(config.uri)

        return {
            "status": "READY",
            "database": CANONICAL_DATABASE,
            "requested_database": requested_database,
            "database_ready": True,
            "canonical_indexes_ready": True,
            "credential_source": "NONE",
            "credential_file_bound": False,
            "local_runtime_user_provisioned": False,
            "maintenance_identity_provisioned": False,
            "existing_database_identity_adopted": False,
            "database_migration_performed": False,
            "bootstrap_scope": ZERO_TOUCH_BOOTSTRAP_SCOPE,
            "canonical_domain_mutations": 0,
            "authorization_model": "HOST_LOCAL_ONLY",
            "legacy_cleanup": cleanup,
            "host_migration": host_migration,
            "rule": (
                "ZERO_TOUCH_LOCAL_HOST; LOOPBACK_ONLY; NO_CREDENTIALS; "
                "NO_DATABASE_ADOPTION; LEGACY_DATABASES_ARE_NEVER_AUTO_REPAIRED"
            ),
        }
    except Exception as exc:
        mapped = _map_failure(exc)
        if mapped is exc:
            raise
        raise mapped from exc
