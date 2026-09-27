from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any

from .ids import new_id
from .models import utcnow
from .schema import CURRENT_SCHEMA_VERSION

BTTM_PROTOCOL_VERSION = "BTTM/1"
SUPPORT_STATES = {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "REVALIDATION_REQUIRED"}


def _as_utc(value: datetime | str | None, *, default: datetime | None = None) -> datetime | None:
    if value is None:
        return default
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _contains(moment: datetime, start: datetime | None, end: datetime | None) -> bool:
    return (start is None or start <= moment) and (end is None or moment < end)


def _base_doc() -> dict[str, Any]:
    now = utcnow()
    return {
        "entity_id": new_id(),
        "schema_version": CURRENT_SCHEMA_VERSION,
        "revision": 0,
        "created_at": now,
        "updated_at": now,
    }


class BitemporalTruthService:
    """BTTM/1: bitemporal, provenance-preserving truth maintenance over MangoMe state.

    Truth assertions are canonical claims about a subject/predicate/value tuple. They are
    not model confidence scores. `valid_*` describes when the assertion is claimed to be
    true in the represented world; `known_*` describes when MangoMe's canonical ledger
    knew that assertion version. Invalidating an assertion closes its known-time interval
    and marks dependent current assertions for revalidation; historical rows remain queryable.
    """

    def __init__(self, service: Any) -> None:
        self.service = service
        self.store = service.store

    def _work(self, work_ref: str) -> dict[str, Any]:
        resolver = getattr(self.service, "_resolve_work", None)
        if callable(resolver):
            return resolver(work_ref)
        direct = self.store.get("work_identities", work_ref)
        if direct:
            return direct
        rows = self.store.find("work_identities", {"work_key": work_ref})
        if len(rows) != 1:
            raise KeyError(f"unknown or ambiguous work identity {work_ref!r}")
        return rows[0]

    def _assertion(self, assertion_id: str) -> dict[str, Any]:
        row = self.store.get("truth_assertions", assertion_id)
        if row is None:
            raise KeyError(f"unknown truth assertion {assertion_id}")
        return row

    def record_assertion(
        self,
        *,
        work_ref: str,
        subject_id: str,
        predicate: str,
        value: Any,
        actor_id: str,
        turn_id: str,
        assertion_key: str | None = None,
        valid_from: datetime | str | None = None,
        valid_to: datetime | str | None = None,
        known_from: datetime | str | None = None,
        evidence_ids: list[str] | None = None,
        support_ids: list[str] | None = None,
        assumption_ids: list[str] | None = None,
        depends_on: list[str] | None = None,
        contradicts: list[str] | None = None,
        source_ref: str | None = None,
        supersedes_assertion_id: str | None = None,
    ) -> dict[str, Any]:
        work = self._work(work_ref)
        require_turn = getattr(self.service, "_require_work_turn", None)
        if callable(require_turn):
            require_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"VERIFY", "MODIFY"})
        now = _as_utc(known_from, default=utcnow())
        vf = _as_utc(valid_from)
        vt = _as_utc(valid_to)
        if vf and vt and vt <= vf:
            raise ValueError("valid_to must be later than valid_from")
        for ref in list(support_ids or []) + list(assumption_ids or []) + list(depends_on or []) + list(contradicts or []):
            self._assertion(str(ref))
        for evidence_id in evidence_ids or []:
            if self.store.get("evidence", str(evidence_id)) is None:
                raise KeyError(f"unknown evidence {evidence_id}")
        key = str(assertion_key or f"{subject_id}:{predicate}").strip()
        if not key:
            raise ValueError("assertion_key is required")

        # A correction/replacement closes only the transaction-time visibility of the
        # superseded assertion. The historical row remains intact for known-at queries.
        superseded_for_propagation: str | None = None
        if supersedes_assertion_id:
            previous = self._assertion(supersedes_assertion_id)
            if previous.get("work_id") != work["entity_id"]:
                raise ValueError("superseded assertion belongs to another WorkIdentity")
            if previous.get("known_to") is None:
                self.store.update(
                    "truth_assertions",
                    previous["entity_id"],
                    {
                        "known_to": now,
                        "lifecycle": "SUPERSEDED",
                        "updated_at": utcnow(),
                    },
                    expected_revision=int(previous.get("revision", 0)),
                )
                superseded_for_propagation = str(previous["entity_id"])

        doc = {
            **_base_doc(),
            "work_id": work["entity_id"],
            "assertion_key": key,
            "subject_id": str(subject_id),
            "predicate": str(predicate),
            "value": value,
            "valid_from": vf,
            "valid_to": vt,
            "known_from": now,
            "known_to": None,
            "evidence_ids": sorted({str(x) for x in (evidence_ids or [])}),
            "support_ids": sorted({str(x) for x in (support_ids or [])}),
            "assumption_ids": sorted({str(x) for x in (assumption_ids or [])}),
            "depends_on": sorted({str(x) for x in (depends_on or [])}),
            "contradicts": sorted({str(x) for x in (contradicts or [])}),
            "source_ref": source_ref,
            "actor_id": actor_id,
            "turn_id": turn_id,
            "supersedes_assertion_id": supersedes_assertion_id,
            "lifecycle": "ACTIVE",
            "support_state": "REVALIDATION_REQUIRED",
            "validity_status": "CURRENT",
            "persistence_level": "CANONICAL",
            "protocol": BTTM_PROTOCOL_VERSION,
        }
        saved = self.store.insert("truth_assertions", doc)
        evaluated = self.evaluate(saved["entity_id"], valid_at=vf or now, known_at=now)
        saved = self.store.update(
            "truth_assertions",
            saved["entity_id"],
            {"support_state": evaluated["support_state"], "updated_at": utcnow()},
            expected_revision=int(saved.get("revision", 0)),
        )
        self._event(
            work_id=work["entity_id"], assertion_id=saved["entity_id"], actor_id=actor_id,
            event_type="ASSERTED", reason=source_ref or "record_assertion", occurred_at=now,
        )
        revalidation_frontier: list[str] = []
        if superseded_for_propagation:
            revalidation_frontier = self._propagate_revalidation(
                superseded_for_propagation, actor_id=actor_id, reason="support assertion superseded"
            )
        return {"assertion": saved, "evaluation": evaluated, "revalidation_frontier": revalidation_frontier}

    def _event(
        self,
        *,
        work_id: str,
        assertion_id: str,
        actor_id: str,
        event_type: str,
        reason: str,
        occurred_at: datetime | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.store.insert("truth_events", {
            **_base_doc(),
            "work_id": work_id,
            "assertion_id": assertion_id,
            "actor_id": actor_id,
            "event_type": event_type,
            "reason": reason,
            "occurred_at": occurred_at or utcnow(),
            "payload": dict(payload or {}),
            "persistence_level": "CANONICAL",
            "protocol": BTTM_PROTOCOL_VERSION,
        })

    def _evidence_supports(self, row: dict[str, Any]) -> tuple[bool, list[str]]:
        failed: list[str] = []
        for evidence_id in row.get("evidence_ids") or []:
            evidence = self.store.get("evidence", str(evidence_id))
            if evidence is None:
                failed.append(str(evidence_id))
                continue
            verdict = str(evidence.get("verdict") or "UNKNOWN").upper()
            if verdict not in {"PASS", "INFO"}:
                failed.append(str(evidence_id))
        return not failed, failed

    def evaluate(
        self,
        assertion_id: str,
        *,
        valid_at: datetime | str | None = None,
        known_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        valid_moment = _as_utc(valid_at, default=utcnow())
        known_moment = _as_utc(known_at, default=utcnow())
        memo: dict[str, tuple[str, list[dict[str, Any]]]] = {}
        stack: set[str] = set()

        def visit(current_id: str) -> tuple[str, list[dict[str, Any]]]:
            if current_id in memo:
                return memo[current_id]
            if current_id in stack:
                result = ("REVALIDATION_REQUIRED", [{"assertion_id": current_id, "reason": "SUPPORT_CYCLE"}])
                memo[current_id] = result
                return result
            row = self._assertion(current_id)
            stack.add(current_id)
            reasons: list[dict[str, Any]] = []
            k_from = _as_utc(row.get("known_from"))
            k_to = _as_utc(row.get("known_to"))
            v_from = _as_utc(row.get("valid_from"))
            v_to = _as_utc(row.get("valid_to"))
            if not _contains(known_moment, k_from, k_to):
                state = "UNSUPPORTED"
                reasons.append({"assertion_id": current_id, "reason": "NOT_KNOWN_AT_TIME"})
            elif not _contains(valid_moment, v_from, v_to):
                state = "UNSUPPORTED"
                reasons.append({"assertion_id": current_id, "reason": "NOT_VALID_AT_TIME"})
            elif str(row.get("lifecycle") or "ACTIVE") == "RETRACTED":
                state = "UNSUPPORTED"
                reasons.append({"assertion_id": current_id, "reason": "RETRACTED"})
            else:
                contradicted_by: list[str] = []
                for ref in row.get("contradicts") or []:
                    try:
                        ref_state, _ = visit(str(ref))
                    except KeyError:
                        ref_state = "REVALIDATION_REQUIRED"
                    if ref_state == "SUPPORTED":
                        contradicted_by.append(str(ref))
                if contradicted_by:
                    state = "CONTRADICTED"
                    reasons.append({"assertion_id": current_id, "reason": "ACTIVE_CONTRADICTION", "refs": contradicted_by})
                else:
                    evidence_ok, bad_evidence = self._evidence_supports(row)
                    unresolved: list[str] = []
                    for field in ("support_ids", "assumption_ids", "depends_on"):
                        for ref in row.get(field) or []:
                            try:
                                ref_state, _ = visit(str(ref))
                            except KeyError:
                                ref_state = "REVALIDATION_REQUIRED"
                            if ref_state != "SUPPORTED":
                                unresolved.append(str(ref))
                    if bad_evidence:
                        unresolved.extend(bad_evidence)
                    # Leaf observations may be supportable without another assertion when
                    # they carry evidence. A bare worker assertion with neither evidence nor
                    # support is intentionally not elevated into truth.
                    has_ground = bool(row.get("evidence_ids") or row.get("support_ids") or row.get("assumption_ids") or row.get("depends_on"))
                    if unresolved:
                        state = "REVALIDATION_REQUIRED"
                        reasons.append({"assertion_id": current_id, "reason": "SUPPORT_NOT_CURRENT", "refs": sorted(set(unresolved))})
                    elif not evidence_ok:
                        state = "REVALIDATION_REQUIRED"
                    elif not has_ground:
                        state = "UNSUPPORTED"
                        reasons.append({"assertion_id": current_id, "reason": "UNGROUNDED_ASSERTION"})
                    else:
                        state = "SUPPORTED"
            stack.remove(current_id)
            memo[current_id] = (state, reasons)
            return memo[current_id]

        state, reasons = visit(assertion_id)
        row = self._assertion(assertion_id)
        return {
            "protocol": BTTM_PROTOCOL_VERSION,
            "assertion_id": assertion_id,
            "work_id": row.get("work_id"),
            "support_state": state,
            "valid_at": valid_moment,
            "known_at": known_moment,
            "reasons": reasons,
            "rule": "TRUTH_MAINTENANCE_DECIDES_SUPPORTABILITY_NOT_RELEVANCE",
        }

    def truth_at(
        self,
        *,
        work_ref: str,
        valid_at: datetime | str | None = None,
        known_at: datetime | str | None = None,
        include_unsupported: bool = False,
    ) -> dict[str, Any]:
        work = self._work(work_ref)
        valid_moment = _as_utc(valid_at, default=utcnow())
        known_moment = _as_utc(known_at, default=utcnow())
        visible: list[dict[str, Any]] = []
        for row in self.store.find("truth_assertions", {"work_id": work["entity_id"]}):
            k_from, k_to = _as_utc(row.get("known_from")), _as_utc(row.get("known_to"))
            v_from, v_to = _as_utc(row.get("valid_from")), _as_utc(row.get("valid_to"))
            if not _contains(known_moment, k_from, k_to) or not _contains(valid_moment, v_from, v_to):
                continue
            evaluation = self.evaluate(row["entity_id"], valid_at=valid_moment, known_at=known_moment)
            if include_unsupported or evaluation["support_state"] == "SUPPORTED":
                visible.append({"assertion": row, "support_state": evaluation["support_state"], "reasons": evaluation["reasons"]})
        visible.sort(key=lambda item: (str(item["assertion"].get("assertion_key")), str(item["assertion"].get("known_from"))))
        return {
            "protocol": BTTM_PROTOCOL_VERSION,
            "work_id": work["entity_id"],
            "valid_at": valid_moment,
            "known_at": known_moment,
            "assertions": visible,
        }

    def current_assertions(self, work_ref: str) -> list[dict[str, Any]]:
        return [item["assertion"] | {"support_state": item["support_state"]} for item in self.truth_at(work_ref=work_ref, include_unsupported=True)["assertions"]]

    def invalidate(
        self,
        *,
        assertion_id: str,
        actor_id: str,
        turn_id: str,
        reason: str,
        known_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        row = self._assertion(assertion_id)
        work = self._work(str(row["work_id"]))
        require_turn = getattr(self.service, "_require_work_turn", None)
        if callable(require_turn):
            require_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"MODIFY"})
        when = _as_utc(known_at, default=utcnow())
        if row.get("known_to") is None:
            row = self.store.update(
                "truth_assertions",
                assertion_id,
                {
                    "known_to": when,
                    "lifecycle": "RETRACTED",
                    "support_state": "UNSUPPORTED",
                    "validity_status": "REVALIDATION_REQUIRED",
                    "updated_at": utcnow(),
                },
                expected_revision=int(row.get("revision", 0)),
            )
        event = self._event(
            work_id=row["work_id"], assertion_id=assertion_id, actor_id=actor_id,
            event_type="INVALIDATED", reason=reason, occurred_at=when,
        )
        impacted = self._propagate_revalidation(assertion_id, actor_id=actor_id, reason=reason)
        return {
            "protocol": BTTM_PROTOCOL_VERSION,
            "assertion": row,
            "event": event,
            "revalidation_frontier": impacted,
        }

    def _propagate_revalidation(self, root_id: str, *, actor_id: str, reason: str) -> list[str]:
        impacted: list[str] = []
        queue: deque[str] = deque([root_id])
        seen = {root_id}
        while queue:
            current = queue.popleft()
            for row in self.store.find("truth_assertions"):
                refs = set(str(x) for field in ("support_ids", "assumption_ids", "depends_on") for x in (row.get(field) or []))
                if current not in refs or row["entity_id"] in seen or row.get("known_to") is not None:
                    continue
                seen.add(row["entity_id"])
                queue.append(row["entity_id"])
                updated = self.store.update(
                    "truth_assertions",
                    row["entity_id"],
                    {
                        "support_state": "REVALIDATION_REQUIRED",
                        "validity_status": "REVALIDATION_REQUIRED",
                        "updated_at": utcnow(),
                    },
                    expected_revision=int(row.get("revision", 0)),
                )
                impacted.append(updated["entity_id"])
                self._event(
                    work_id=updated["work_id"], assertion_id=updated["entity_id"], actor_id=actor_id,
                    event_type="REVALIDATION_REQUIRED", reason=f"dependency invalidated: {reason}",
                    payload={"dependency_assertion_id": current},
                )
        return impacted

    def status(self, *, work_ref: str) -> dict[str, Any]:
        work = self._work(work_ref)
        current = self.current_assertions(work["entity_id"])
        counts: dict[str, int] = {state: 0 for state in SUPPORT_STATES}
        for row in current:
            counts[str(row.get("support_state") or "REVALIDATION_REQUIRED")] = counts.get(str(row.get("support_state")), 0) + 1
        return {
            "protocol": BTTM_PROTOCOL_VERSION,
            "work_id": work["entity_id"],
            "counts": counts,
            "current_assertions": len(current),
            "rule": "VALID_TIME_AND_KNOWN_TIME_ARE_SEPARATE; HISTORY_IS_NEVER_DESTROYED",
        }
