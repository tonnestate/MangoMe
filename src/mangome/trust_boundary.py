from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .operability import OperabilityError

TRUST_BOUNDARY_VERSION = "MTB/1"
_DANGEROUS_BUILTIN_ROLES = {
    "root", "dbOwner", "userAdmin", "userAdminAnyDatabase", "dbAdminAnyDatabase",
    "readWriteAnyDatabase", "clusterAdmin", "hostManager", "restore", "backup",
}


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _mode() -> str:
    value = os.environ.get("MANGOME_TRUST_BOUNDARY", "WARN").strip().upper()
    if value not in {"OFF", "WARN", "STRICT"}:
        raise OperabilityError("TRUST_BOUNDARY_CONFIG_INVALID", f"unsupported MANGOME_TRUST_BOUNDARY={value!r}")
    return value


def _safe_file(path: Path) -> tuple[bool, list[str]]:
    violations: list[str] = []
    try:
        info = path.stat()
    except OSError:
        return False, ["CREDENTIAL_FILE_UNREADABLE"]
    if not stat.S_ISREG(info.st_mode):
        violations.append("CREDENTIAL_FILE_NOT_REGULAR")
    if info.st_mode & 0o077:
        violations.append("CREDENTIAL_FILE_PERMISSIONS_TOO_BROAD")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        violations.append("CREDENTIAL_FILE_OWNER_MISMATCH")
    return not violations, violations


def _endpoint_scope(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme not in {"mongodb", "mongodb+srv"}:
        return "UNKNOWN"
    if parsed.scheme == "mongodb+srv":
        return "REMOTE"
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    hosts = [h for h in netloc.split(",") if h]
    if not hosts:
        return "UNKNOWN"
    scopes: set[str] = set()
    for hostport in hosts:
        host = hostport
        if host.startswith("["):
            host = host.split("]", 1)[0] + "]"
        else:
            host = host.rsplit(":", 1)[0] if ":" in host and host.rsplit(":", 1)[1].isdigit() else host
        host = unquote(host).strip("[]")
        if host.startswith("/"):
            scopes.add("UNIX_SOCKET")
        elif host in {"127.0.0.1", "localhost", "::1"}:
            scopes.add("LOOPBACK")
        else:
            scopes.add("REMOTE")
    if "REMOTE" in scopes:
        return "REMOTE"
    if "UNIX_SOCKET" in scopes:
        return "UNIX_SOCKET"
    return "LOOPBACK"


@dataclass(frozen=True)
class MongoConnectionConfig:
    uri: str
    source: str
    mode: str
    status: dict[str, Any]


def resolve_mongodb_connection() -> MongoConnectionConfig:
    mode = _mode()
    credential_file = os.environ.get("MANGOME_MONGODB_URI_FILE", "").strip()
    env_uri = os.environ.get("MANGOME_MONGODB_URI")
    violations: list[str] = []
    warnings: list[str] = []
    source = "DEFAULT_LOOPBACK"

    if credential_file:
        path = Path(credential_file).expanduser()
        safe, file_violations = _safe_file(path)
        violations.extend(file_violations)
        if not safe and mode == "STRICT":
            raise OperabilityError("TRUST_BOUNDARY_VIOLATION", ",".join(file_violations))
        try:
            uri = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise OperabilityError("TRUST_BOUNDARY_VIOLATION", "MongoDB credential file is unreadable") from exc
        source = "CREDENTIAL_FILE"
    elif env_uri:
        uri = env_uri.strip()
        source = "ENVIRONMENT"
        warnings.append("MONGODB_CREDENTIALS_IN_PROCESS_ENVIRONMENT")
        if mode == "STRICT":
            violations.append("STRICT_MODE_REQUIRES_CREDENTIAL_FILE")
    else:
        uri = "mongodb://127.0.0.1:27017"
        if mode == "STRICT":
            violations.append("STRICT_MODE_REQUIRES_EXPLICIT_CREDENTIAL_FILE")

    expected_uid = os.environ.get("MANGOME_EXPECTED_SERVICE_UID", "").strip()
    current_uid = os.geteuid() if hasattr(os, "geteuid") else None
    if mode == "STRICT":
        if not expected_uid:
            violations.append("STRICT_MODE_REQUIRES_EXPECTED_SERVICE_UID")
        elif current_uid is not None and str(current_uid) != expected_uid:
            violations.append("SERVICE_UID_MISMATCH")

    endpoint_scope = _endpoint_scope(uri)
    if mode == "STRICT" and endpoint_scope == "REMOTE" and not _flag("MANGOME_ALLOW_REMOTE_MONGODB"):
        violations.append("REMOTE_MONGODB_NOT_EXPLICITLY_ALLOWED")

    if mode == "STRICT" and violations:
        raise OperabilityError("TRUST_BOUNDARY_VIOLATION", ",".join(sorted(set(violations))))

    status = {
        "protocol": TRUST_BOUNDARY_VERSION,
        "mode": mode,
        "credential_source": source,
        "credentials_in_environment": source == "ENVIRONMENT",
        "endpoint_scope": endpoint_scope,
        "current_service_uid": current_uid,
        "expected_service_uid_configured": bool(expected_uid),
        "strict_ok": not violations if mode == "STRICT" else None,
        "violations": sorted(set(violations)),
        "warnings": sorted(set(warnings)),
        "rule": "WORKERS_MUST_NOT_POSSESS_CANONICAL_DATABASE_CREDENTIALS",
    }
    return MongoConnectionConfig(uri=uri, source=source, mode=mode, status=status)


def inspect_authenticated_roles(store: Any) -> dict[str, Any]:
    """Best-effort role inspection without exposing principals or credentials."""
    try:
        result = store.db.command("connectionStatus")
        roles = ((result.get("authInfo") or {}).get("authenticatedUserRoles") or [])
    except Exception as exc:  # observability must not make startup depend on role introspection
        return {
            "checked": False,
            "error_type": type(exc).__name__,
            "dangerous_builtin_roles": [],
        }
    role_names = sorted({str(r.get("role")) for r in roles if isinstance(r, dict) and r.get("role")})
    dangerous = sorted(set(role_names) & _DANGEROUS_BUILTIN_ROLES)
    return {
        "checked": True,
        "role_count": len(role_names),
        "dangerous_builtin_roles": dangerous,
        "least_privilege_ok": not dangerous,
    }


def enforce_mongo_role_boundary(store: Any) -> dict[str, Any]:
    report = inspect_authenticated_roles(store)
    if _flag("MANGOME_ENFORCE_LEAST_PRIVILEGE") and report.get("dangerous_builtin_roles"):
        raise OperabilityError(
            "MONGODB_ROLE_BOUNDARY_VIOLATION",
            "MangoMe MongoDB identity has an administrative/global role; use a database-scoped runtime role",
        )
    return report
