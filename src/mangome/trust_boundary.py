from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .operability import OperabilityError

TRUST_BOUNDARY_VERSION = "MTB/2"
LOCAL_HOST_MODE = "LOCAL_HOST"


def _endpoint_scope(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme != "mongodb":
        return "UNSUPPORTED"
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
        if host in {"127.0.0.1", "localhost", "::1"}:
            scopes.add("LOOPBACK")
        else:
            scopes.add("REMOTE")
    if "REMOTE" in scopes:
        return "REMOTE"
    return "LOOPBACK"


def _contains_credentials(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.username is not None or parsed.password is not None:
        return True
    query = {k.lower(): v for k, v in parse_qs(parsed.query).items()}
    return any(k in query for k in {"authsource", "authmechanism", "authmechanismproperties"})


@dataclass(frozen=True)
class MongoConnectionConfig:
    uri: str
    source: str
    mode: str
    status: dict[str, Any]


def resolve_mongodb_connection() -> MongoConnectionConfig:
    """Resolve the v0.3.16 single-host MongoDB binding.

    LOCAL_HOST intentionally has no MongoDB principal, role, password, credential
    file, maintenance identity, credential adoption or offline no-auth recovery.
    Security is the host/network boundary: the MongoDB listener must be loopback-only.
    """

    mode = os.environ.get("MANGOME_TRUST_BOUNDARY", LOCAL_HOST_MODE).strip().upper()
    if mode != LOCAL_HOST_MODE:
        raise OperabilityError(
            "LEGACY_TRUST_MODE_REJECTED",
            "v0.3.16 managed local operation requires MANGOME_TRUST_BOUNDARY=LOCAL_HOST",
        )

    if os.environ.get("MANGOME_MONGODB_URI_FILE", "").strip():
        raise OperabilityError(
            "LEGACY_CREDENTIAL_CONFIGURATION_REJECTED",
            "LOCAL_HOST does not use MANGOME_MONGODB_URI_FILE; remove the stale MangoMe credential binding",
        )

    uri = os.environ.get("MANGOME_MONGODB_URI", "").strip() or "mongodb://127.0.0.1:27017"
    if _contains_credentials(uri):
        raise OperabilityError(
            "LOCAL_HOST_CREDENTIALS_FORBIDDEN",
            "LOCAL_HOST requires a credential-free MongoDB URI",
        )

    endpoint_scope = _endpoint_scope(uri)
    if endpoint_scope != "LOOPBACK":
        raise OperabilityError(
            "LOCAL_HOST_ENDPOINT_REQUIRED",
            "LOCAL_HOST requires MongoDB to be reachable only through a loopback endpoint",
        )

    status = {
        "protocol": TRUST_BOUNDARY_VERSION,
        "mode": LOCAL_HOST_MODE,
        "credential_source": "NONE",
        "credentials_in_environment": False,
        "endpoint_scope": endpoint_scope,
        "authorization_model": "HOST_LOCAL_ONLY",
        "warnings": [],
        "violations": [],
        "rule": "LOOPBACK_ONLY; NO_MONGODB_PRINCIPAL; HOST_IS_THE_TRUST_BOUNDARY",
    }
    return MongoConnectionConfig(uri=uri, source="LOCAL_HOST_LOOPBACK", mode=mode, status=status)


def inspect_authenticated_roles(store: Any) -> dict[str, Any]:
    """Verify that LOCAL_HOST is genuinely unauthenticated and not role-backed."""

    try:
        # This command requires database visibility when authorization is enabled.
        # In LOCAL_HOST it must succeed without credentials.
        store.client.list_database_names()
        result = store.db.command("connectionStatus")
        roles = ((result.get("authInfo") or {}).get("authenticatedUserRoles") or [])
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code in {13, 18} or type(exc).__name__ in {"AuthenticationFailure", "OperationFailure"}:
            raise OperabilityError(
                "LOCAL_HOST_MONGODB_AUTHORIZATION_ENABLED",
                "MongoDB still requires authorization; LOCAL_HOST requires loopback-only MongoDB with authorization disabled",
            ) from exc
        raise

    normalized = [
        {"role": str(r.get("role")), "db": str(r.get("db"))}
        for r in roles
        if isinstance(r, dict) and r.get("role")
    ]
    if normalized:
        raise OperabilityError(
            "LOCAL_HOST_AUTHENTICATED_IDENTITY_FORBIDDEN",
            "LOCAL_HOST must not run with an authenticated MongoDB identity",
        )

    return {
        "checked": True,
        "role_count": 0,
        "authenticated_roles": [],
        "least_privilege_ok": True,
        "authorization_model": "HOST_LOCAL_ONLY",
    }


def enforce_mongo_role_boundary(store: Any) -> dict[str, Any]:
    return inspect_authenticated_roles(store)
