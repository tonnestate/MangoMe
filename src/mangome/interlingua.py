from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any

from .context import ContextCompiler
from .service import MangoMeService

UAI_VERSION = "UAI/1"
UAI_RESULT_VERSION = "UAI/1R"
UAI_PROFILE = "mangome-work"

_RULES = [
    "DONE_CLAIMED!=VERIFIED",
    "MUTATE_REQUIRES_ACTIVE_PLAN",
    "UNATTESTED_EVIDENCE!=PROOF",
    "COLLISION_WARNING=CONTINUE_ALLOWED",
]

_RESULT_STATUSES = {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED"}
_ACTION_SPECS: dict[str, tuple[str, int, int]] = {
    # code: (expanded type, minimum array length, maximum array length)
    "P": ("PROGRESS", 3, 4),
    "A": ("ARTIFACT", 5, 6),
    "E": ("EVIDENCE", 5, 6),
    "D": ("DONE_CLAIM", 1, 2),
    "N": ("DISCOVER_SLICE", 3, 4),
    "B": ("BLOCKER", 2, 2),
}


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _wire_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _estimated_tokens(chars: int) -> int:
    # Provider tokenizers differ. This deliberately remains a labelled heuristic;
    # actual token counts belong in ExecutionReceipt telemetry.
    return max(1, math.ceil(chars / 4)) if chars else 0


def _as_value(value: Any) -> Any:
    return getattr(value, "value", value)


class InterlinguaError(ValueError):
    pass


class UAICompiler:
    """Deterministic MangoMe UAI/1 semantic transport.

    UAI/1 is not a replacement for canonical MangoMe documents. It is a compact,
    versioned execution projection intended for model transport. Canonical state
    remains in MangoMe; UAI packets are disposable and hash-bound to their source
    semantics.
    """

    def __init__(self, service: MangoMeService) -> None:
        self.service = service
        self.context = ContextCompiler(service)

    def semantic_projection(self, family_id: str, slice_id: str | None = None) -> dict[str, Any]:
        packet = self.context.compile(family_id, slice_id)
        state = packet["current_state"]
        effective = packet["effective_family"]
        spec = packet.get("current_spec")
        sl = packet.get("current_slice")

        projection: dict[str, Any] = {
            "family": {
                "id": packet["family"]["entity_id"],
                "key": packet["family"]["family_key"],
                "title": packet["family"]["title"],
                "scopes": list(packet["family"].get("scope_ids", [])),
            },
            "state": {
                "execution": _as_value(state.get("execution_state")),
                "assurance": _as_value(state.get("assurance_state")),
                "last_started": state.get("last_started_slice_id"),
                "active": list(state.get("active_slice_ids", [])),
                "last_done": state.get("last_done_claimed_slice_id"),
                "last_verified": state.get("last_verified_slice_id"),
                "next": list(state.get("next_known_slice_ids", [])),
                "actors": list(state.get("active_actor_ids", [])),
                "warnings": list(state.get("warnings", [])),
            },
            "effective": {
                "active_contracts": list(effective.get("effective_contract_ids", [])),
                "superseded": list(effective.get("superseded_contract_ids", [])),
                "conflicted": bool(effective.get("is_conflicted")),
            },
            "spec": None,
            "slice": None,
            "contracts": [
                {
                    "id": c["entity_id"],
                    "declared": c.get("declared_id"),
                    "kind": _as_value(c.get("kind")),
                    "title": c.get("title"),
                }
                for c in packet.get("relevant_contracts", [])
            ],
            "evidence": [
                {
                    "id": e["entity_id"],
                    "class": _as_value(e.get("evidence_class")),
                    "verdict": _as_value(e.get("verdict")),
                    "trust": _as_value(e.get("trust")),
                    "source": e.get("source"),
                    "result": e.get("result"),
                }
                for e in packet.get("evidence", [])
            ],
            "rules": list(_RULES),
        }

        if spec:
            projection["spec"] = {
                "id": spec["entity_id"],
                "version": spec.get("version"),
                "objective": spec.get("objective"),
                "deliverables": list(spec.get("deliverables", [])),
                "constraints": list(spec.get("constraints", [])),
                "acceptance": list(spec.get("acceptance_criteria", [])),
                "required_evidence": list(spec.get("required_evidence", [])),
            }

        if sl:
            dependencies = sl.get("dependency_requirements") or [
                {"slice_id": dep, "required_level": "DONE_CLAIMED"}
                for dep in sl.get("depends_on", [])
            ]
            projection["slice"] = {
                "id": sl["entity_id"],
                "declared": sl.get("declared_id"),
                "title": sl.get("title"),
                "objective": sl.get("objective"),
                "execution": _as_value(sl.get("execution_state")),
                "assurance": _as_value(sl.get("assurance_state")),
                "plan": sl.get("active_plan_id"),
                "step": sl.get("current_step"),
                "steps": sl.get("total_steps"),
                "blocker": sl.get("blocker"),
                "dependencies": [
                    {
                        "id": dep.get("slice_id"),
                        "level": _as_value(dep.get("required_level")),
                    }
                    for dep in dependencies
                ],
                "gates": [
                    {
                        "id": gate.get("gate_id"),
                        "status": gate.get("status"),
                        "description": gate.get("description"),
                        "evidence": list(gate.get("evidence_ids", [])),
                    }
                    for gate in sl.get("gates", [])
                ],
            }
        return projection

    @staticmethod
    def encode_projection(projection: dict[str, Any]) -> dict[str, Any]:
        family = projection["family"]
        state = projection["state"]
        effective = projection["effective"]
        spec = projection.get("spec")
        sl = projection.get("slice")

        compact: dict[str, Any] = {
            "v": UAI_VERSION,
            "p": UAI_PROFILE,
            "h": _hash(projection),
            "f": [family["id"], family["key"], family["title"], family["scopes"]],
            "s": [
                state["execution"], state["assurance"], state["last_started"], state["active"],
                state["last_done"], state["last_verified"], state["next"], state["actors"], state["warnings"],
            ],
            "ef": [effective["active_contracts"], effective["superseded"], effective["conflicted"]],
            "sp": None if spec is None else [
                spec["id"], spec["version"], spec["objective"], spec["deliverables"],
                spec["constraints"], spec["acceptance"], spec["required_evidence"],
            ],
            "w": None,
            "c": [[c["id"], c["declared"], c["kind"], c["title"]] for c in projection["contracts"]],
            "e": [[e["id"], e["class"], e["verdict"], e["trust"], e["source"], e["result"]] for e in projection["evidence"]],
            "r": projection["rules"],
        }
        if sl is not None:
            compact["w"] = [
                sl["id"], sl["declared"], sl["title"], sl["objective"], sl["execution"], sl["assurance"],
                sl["plan"], sl["step"], sl["steps"], sl["blocker"],
                [[d["id"], d["level"]] for d in sl["dependencies"]],
                [[g["id"], g["status"], g["description"], g["evidence"]] for g in sl["gates"]],
            ]
        return compact

    @staticmethod
    def decode_context(packet: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(packet, str):
            try:
                data = json.loads(packet)
            except json.JSONDecodeError as exc:
                raise InterlinguaError(f"invalid UAI JSON: {exc}") from exc
        else:
            data = dict(packet)
        if data.get("v") != UAI_VERSION or data.get("p") != UAI_PROFILE:
            raise InterlinguaError("unsupported UAI context version/profile")
        try:
            f = data["f"]
            s = data["s"]
            ef = data["ef"]
            sp = data.get("sp")
            w = data.get("w")
            projection: dict[str, Any] = {
                "family": {"id": f[0], "key": f[1], "title": f[2], "scopes": f[3]},
                "state": {
                    "execution": s[0], "assurance": s[1], "last_started": s[2], "active": s[3],
                    "last_done": s[4], "last_verified": s[5], "next": s[6], "actors": s[7], "warnings": s[8],
                },
                "effective": {"active_contracts": ef[0], "superseded": ef[1], "conflicted": ef[2]},
                "spec": None,
                "slice": None,
                "contracts": [
                    {"id": row[0], "declared": row[1], "kind": row[2], "title": row[3]}
                    for row in data.get("c", [])
                ],
                "evidence": [
                    {"id": row[0], "class": row[1], "verdict": row[2], "trust": row[3], "source": row[4], "result": row[5]}
                    for row in data.get("e", [])
                ],
                "rules": list(data.get("r", [])),
            }
            if sp is not None:
                projection["spec"] = {
                    "id": sp[0], "version": sp[1], "objective": sp[2], "deliverables": sp[3],
                    "constraints": sp[4], "acceptance": sp[5], "required_evidence": sp[6],
                }
            if w is not None:
                projection["slice"] = {
                    "id": w[0], "declared": w[1], "title": w[2], "objective": w[3],
                    "execution": w[4], "assurance": w[5], "plan": w[6], "step": w[7], "steps": w[8],
                    "blocker": w[9],
                    "dependencies": [{"id": row[0], "level": row[1]} for row in w[10]],
                    "gates": [
                        {"id": row[0], "status": row[1], "description": row[2], "evidence": row[3]}
                        for row in w[11]
                    ],
                }
        except (IndexError, KeyError, TypeError) as exc:
            raise InterlinguaError("malformed UAI context packet") from exc

        expected = data.get("h")
        actual = _hash(projection)
        if expected != actual:
            raise InterlinguaError("UAI semantic hash mismatch")
        return projection

    def compile(self, family_id: str, slice_id: str | None = None) -> dict[str, Any]:
        raw = self.context.compile(family_id, slice_id)
        projection = self.semantic_projection(family_id, slice_id)
        compact = self.encode_projection(projection)
        wire = _wire_json(compact)
        raw_wire = _wire_json(raw)
        raw_chars = len(raw_wire)
        wire_chars = len(wire)
        return {
            "protocol": UAI_VERSION,
            "profile": UAI_PROFILE,
            "semantic_hash": compact["h"],
            "wire": wire,
            "packet": compact,
            "metrics": {
                "raw_context_chars": raw_chars,
                "uai_chars": wire_chars,
                "char_savings": max(0, raw_chars - wire_chars),
                "char_reduction_pct": round(max(0.0, (raw_chars - wire_chars) / raw_chars * 100.0), 2) if raw_chars else 0.0,
                "estimated_raw_tokens": _estimated_tokens(raw_chars),
                "estimated_uai_tokens": _estimated_tokens(wire_chars),
                "estimated_token_savings": max(0, _estimated_tokens(raw_chars) - _estimated_tokens(wire_chars)),
                "token_estimate_note": "character/4 heuristic only; store provider-reported token counts in ExecutionReceipt",
            },
        }


def decode_uai_result(payload: str | dict[str, Any], *, expected_context_hash: str | None = None) -> dict[str, Any]:
    if expected_context_hash is None:
        raise InterlinguaError(
            "expected_context_hash is required for UAI/1R decoding; unbound results may be stale"
        )
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise InterlinguaError(f"invalid UAI result JSON: {exc}") from exc
    else:
        data = dict(payload)
    if data.get("v") != UAI_RESULT_VERSION:
        raise InterlinguaError("unsupported UAI result version")
    context_hash = data.get("h")
    if not isinstance(context_hash, str) or len(context_hash) != 64:
        raise InterlinguaError("UAI result requires a 64-character context hash")
    if expected_context_hash is not None and context_hash != expected_context_hash:
        raise InterlinguaError("UAI result context hash does not match expected context")
    status = str(data.get("st") or "").upper()
    if status not in _RESULT_STATUSES:
        raise InterlinguaError(f"unsupported UAI result status {status!r}")
    summary = data.get("sum")
    if summary is not None and not isinstance(summary, str):
        raise InterlinguaError("UAI result summary must be a string")

    actions: list[dict[str, Any]] = []
    for raw in data.get("a", []):
        if not isinstance(raw, list) or not raw or raw[0] not in _ACTION_SPECS:
            raise InterlinguaError("unsupported or malformed UAI result action")
        code = raw[0]
        action_type, minimum, maximum = _ACTION_SPECS[code]
        if not minimum <= len(raw) <= maximum:
            raise InterlinguaError(f"UAI action {code} has invalid arity")
        if code == "P":
            actions.append({"type": action_type, "current_step": raw[1], "total_steps": raw[2], "blocker": raw[3] if len(raw) > 3 else None})
        elif code == "A":
            actions.append({
                "type": action_type, "logical_name": raw[1], "artifact_type": raw[2], "storage_system": raw[3],
                "physical_location": raw[4], "checksum": raw[5] if len(raw) > 5 else None,
            })
        elif code == "E":
            actions.append({
                "type": action_type, "evidence_type": raw[1], "evidence_class": raw[2], "source": raw[3],
                "result": raw[4], "artifact_id": raw[5] if len(raw) > 5 else None,
            })
        elif code == "D":
            actions.append({"type": action_type, "summary": raw[1] if len(raw) > 1 else None})
        elif code == "N":
            actions.append({"type": action_type, "declared_id": raw[1], "title": raw[2], "objective": raw[3] if len(raw) > 3 else None})
        elif code == "B":
            actions.append({"type": action_type, "blocker": raw[1]})
    return {
        "protocol": UAI_RESULT_VERSION,
        "context_hash": context_hash,
        "status": status,
        "summary": summary,
        "actions": actions,
        "note": "Decoded result is a proposal only; route actions through normal MangoMe mutation/assurance tools.",
    }


def render_uai_result(payload: str | dict[str, Any], *, language: str = "en", expected_context_hash: str | None = None) -> str:
    decoded = decode_uai_result(payload, expected_context_hash=expected_context_hash)
    lang = language.lower()
    if lang not in {"en", "de"}:
        raise InterlinguaError("deterministic renderer currently supports only 'en' and 'de'")

    if lang == "de":
        status_labels = {"SUCCESS": "Erfolgreich", "PARTIAL": "Teilweise", "BLOCKED": "Blockiert", "FAILED": "Fehlgeschlagen"}
        lines = [f"Status: {status_labels[decoded['status']]}."]
        if decoded.get("summary"):
            lines.append(f"Zusammenfassung: {decoded['summary']}")
        for action in decoded["actions"]:
            typ = action["type"]
            if typ == "PROGRESS":
                lines.append(f"Fortschritt: Schritt {action['current_step']} von {action['total_steps']}.")
                if action.get("blocker"):
                    lines.append(f"Blocker: {action['blocker']}")
            elif typ == "ARTIFACT":
                lines.append(f"Artefakt: {action['logical_name']} ({action['artifact_type']}) unter {action['physical_location']}.")
            elif typ == "EVIDENCE":
                lines.append(f"Evidence: {action['evidence_type']} aus {action['source']} mit Ergebnis {action['result']}.")
            elif typ == "DONE_CLAIM":
                lines.append("Der Worker meldet DONE_CLAIMED; dies ist noch keine Verifikation.")
                if action.get("summary"):
                    lines.append(f"Worker-Zusammenfassung: {action['summary']}")
            elif typ == "DISCOVER_SLICE":
                lines.append(f"Neuer möglicher Slice: {action['declared_id']} — {action['title']}.")
            elif typ == "BLOCKER":
                lines.append(f"Blocker: {action['blocker']}")
        return "\n".join(lines)

    lines = [f"Status: {decoded['status'].title()}."]
    if decoded.get("summary"):
        lines.append(f"Summary: {decoded['summary']}")
    for action in decoded["actions"]:
        typ = action["type"]
        if typ == "PROGRESS":
            lines.append(f"Progress: step {action['current_step']} of {action['total_steps']}.")
            if action.get("blocker"):
                lines.append(f"Blocker: {action['blocker']}")
        elif typ == "ARTIFACT":
            lines.append(f"Artifact: {action['logical_name']} ({action['artifact_type']}) at {action['physical_location']}.")
        elif typ == "EVIDENCE":
            lines.append(f"Evidence: {action['evidence_type']} from {action['source']} with result {action['result']}.")
        elif typ == "DONE_CLAIM":
            lines.append("The worker claims DONE_CLAIMED; this is not verification.")
            if action.get("summary"):
                lines.append(f"Worker summary: {action['summary']}")
        elif typ == "DISCOVER_SLICE":
            lines.append(f"Potential new slice: {action['declared_id']} — {action['title']}.")
        elif typ == "BLOCKER":
            lines.append(f"Blocker: {action['blocker']}")
    return "\n".join(lines)
