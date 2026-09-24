from __future__ import annotations

import os
import secrets


class CapabilityDenied(PermissionError):
    pass


def _allowed(actor_id: str, env_name: str) -> bool:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return True
    return actor_id in {item.strip() for item in raw.split(",") if item.strip()}


def _role_authorized(required_role: str, actor_id: str) -> bool:
    role = os.environ.get("MANGOME_RUNTIME_ROLE", "WORKER").strip().upper()
    if role not in {required_role, "FULL"}:
        return False
    runtime_actor = os.environ.get("MANGOME_RUNTIME_ACTOR", "").strip()
    if not runtime_actor:
        raise CapabilityDenied("MANGOME_RUNTIME_ACTOR is required for privileged runtime roles")
    if runtime_actor != actor_id:
        raise CapabilityDenied(f"runtime actor is {runtime_actor!r}, not {actor_id!r}")
    return True


def _require(expected_env: str, actor_env: str, actor_id: str, presented_token: str | None, label: str, role: str) -> None:
    if _role_authorized(role, actor_id):
        return
    expected = os.environ.get(expected_env)
    if not expected:
        raise CapabilityDenied(
            f"{label} capability is disabled: use a {role} runtime role or configure {expected_env}"
        )
    if not presented_token or not secrets.compare_digest(expected, presented_token):
        raise CapabilityDenied(f"invalid {label} capability")
    if not _allowed(actor_id, actor_env):
        raise CapabilityDenied(f"actor {actor_id!r} is not allowed for {label}")


def require_verifier(actor_id: str, token: str | None = None) -> None:
    _require(
        "MANGOME_VERIFIER_TOKEN", "MANGOME_VERIFIER_ACTORS",
        actor_id, token, "verification", "VERIFIER",
    )


def require_approver(actor_id: str, token: str | None = None) -> None:
    _require(
        "MANGOME_APPROVAL_TOKEN", "MANGOME_APPROVER_ACTORS",
        actor_id, token, "approval", "OWNER",
    )
