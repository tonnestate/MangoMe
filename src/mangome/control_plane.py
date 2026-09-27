from __future__ import annotations

import re
from typing import Any


_TARGET_RE = re.compile(r"\bmango\s*me\b|\bmangome\b", re.IGNORECASE)
_MAINTENANCE_RE = re.compile(
    r"\b(?:"
    r"update|upgrade|install|reinstall|repair|hotfix|patch|rollback|roll\s*back|"
    r"reconfigure|configure|autostart|service|runtime|version|deploy|deployment|"
    r"aktualisier\w*|updat\w*|upgrad\w*|installier\w*|reparier\w*|"
    r"patch\w*|hotfix\w*|rollback\w*|zur(?:ue|ü)ckroll\w*|"
    r"konfigurier\w*|autostart\w*|dienst\w*|laufzeit\w*|version\w*"
    r")\b",
    re.IGNORECASE,
)
_DB_WORD_RE = re.compile(r"\b(?:database|db|mongodb|datenbank)\b", re.IGNORECASE)
_DB_MUTATION_RE = re.compile(
    r"\b(?:änder\w*|aender\w*|veränder\w*|veraender\w*|change\w*|touch\w*|modify\w*|write\w*)\b",
    re.IGNORECASE,
)
_DB_NEGATION_RE = re.compile(r"\b(?:nicht|not|no|kein\w*|ohne|never)\b|do\s+not|don't|dont", re.IGNORECASE)



def is_mangome_self_maintenance_request(request_text: str, *, target: str | None = None) -> bool:
    """Return True only for explicit MangoMe control-plane maintenance intent.

    The classifier is deliberately narrow. Mentioning MangoMe, asking about status, or
    ordinary MangoMe-managed project work does not qualify. The user must explicitly
    target MangoMe itself with a maintenance verb.
    """
    text = str(request_text or "").strip()
    if not text:
        return False
    explicit_target = bool(_TARGET_RE.search(text))
    resolved_target = bool(_TARGET_RE.search(str(target or "")))
    return bool((explicit_target or resolved_target) and _MAINTENANCE_RE.search(text))


def database_changes_explicitly_disallowed(request_text: str) -> bool:
    """Detect an explicit no-database-change constraint in English or German.

    Keep this deliberately local: a database term, a mutation verb, and a negation must
    occur in the same short clause/window. This handles both "do not change the DB" and
    German word orders such as "verändere die Datenbank nicht".
    """
    text = str(request_text or "")
    for match in _DB_WORD_RE.finditer(text):
        lo = max(0, match.start() - 80)
        hi = min(len(text), match.end() + 80)
        window = text[lo:hi]
        if _DB_MUTATION_RE.search(window) and _DB_NEGATION_RE.search(window):
            return True
    return False


def control_plane_maintenance_result(request_text: str, *, workspace_root: str) -> dict[str, Any]:
    """Return the CPM/1 out-of-band self-maintenance disposition.

    This function is intentionally pure/read-only. It does not create WorkIdentity,
    Contracts, Plans, Slices, approvals, receipts, or database state. Explicit operator
    intent governs only the named MangoMe control-plane surface. If a target update
    requires a database/schema migration, the worker must stop and report that fact
    instead of manufacturing an approval or writing the database.
    """
    db_disallowed = database_changes_explicitly_disallowed(request_text)
    return {
        "reconciliation_protocol": "CPM/1",
        "rule": "SELF_MAINTENANCE_MUST_NOT_REQUIRE_SELF_ADMISSION",
        "request_is_canonical_truth": False,
        "out_of_band_control_plane_maintenance": True,
        "project_work_admission_required": False,
        "enter_work_required": False,
        "work_identity_required": False,
        "controller_database_grant_required": False,
        "workspace_root": workspace_root,
        "database_changes_explicitly_disallowed": db_disallowed,
        "database_write_allowed_by_this_disposition": False,
        "allowed_scope": [
            "MangoMe source checkout",
            "MangoMe virtual environment/package installation",
            "MangoMe MCP launcher/runtime configuration",
            "MangoMe service/autostart configuration",
        ],
        "forbidden_scope": [
            "application/project code not explicitly targeted by the maintenance request",
            "canonical MangoMe WorkIdentity/Contract/Specification/Plan/Slice state",
            "MongoDB data or schema unless separately and explicitly authorized",
        ],
        "stop_conditions": [
            "target update requires a MongoDB/schema migration while database changes are not explicitly authorized",
            "maintenance would exceed the explicitly requested MangoMe control-plane scope",
            "target source/version cannot be established from a current authoritative source",
        ],
        "next_action": (
            "Perform only the explicitly requested MangoMe self-maintenance using current runtime/repository evidence. "
            "Do not call enter_work, create governance state, or write a self-approval to MangoMe. "
            "If a database/schema migration is required, stop immediately and report DATABASE_CHANGE_REQUIRED."
        ),
    }
