from __future__ import annotations

import hashlib
from typing import Any

from .authority import CapabilityDenied, require_verifier
from .enums import EffectOutcome, EffectRecoveryStrategy, EffectState
from .ids import new_id
from .models import utcnow
from .schema import CURRENT_SCHEMA_VERSION
from .service import ApprovalRequired, InvalidTransition


def _base_doc() -> dict[str, Any]:
    now = utcnow()
    return {
        "entity_id": new_id(),
        "schema_version": CURRENT_SCHEMA_VERSION,
        "revision": 0,
        "created_at": now,
        "updated_at": now,
    }


def unresolved_required_effects(service: Any, slice_id: str) -> list[dict[str, Any]]:
    """Return required logical effects that still block Slice closure."""
    rows = service.store.find("effects", {"slice_id": slice_id})
    return [
        row
        for row in rows
        if bool(row.get("required_for_closure", True))
        and not (
            row.get("state") == EffectState.RECONCILED.value
            and row.get("satisfied") is True
        )
    ]


class EffectJournalService:
    """PER/1 durable intent and reconciliation for external side effects.

    MangoMe does not claim a cross-system ACID transaction. Instead, every governed
    external effect receives durable intent before dispatch and remains recoverable
    until observed reality is reconciled with that intent.
    """

    def __init__(self, service: Any) -> None:
        self.service = service

    def _work_for_slice(self, slice_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        sl = self.service._must_get("slices", slice_id)
        resolver = getattr(self.service, "_work_for_slice", None)
        work = resolver(slice_id) if callable(resolver) else None
        if work is None:
            raise InvalidTransition("PER/1 requires an admitted WorkIdentity")
        return sl, work

    def _require_turn(
        self,
        *,
        slice_id: str,
        actor_id: str,
        turn_id: str,
        allowed_modes: set[str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sl, work = self._work_for_slice(slice_id)
        require_turn = getattr(self.service, "_require_work_turn", None)
        if not callable(require_turn):
            raise InvalidTransition("PER/1 requires WorkTurn enforcement")
        require_turn(
            work_id=work["entity_id"],
            turn_id=turn_id,
            actor_id=actor_id,
            allowed_modes=allowed_modes,
        )
        return sl, work

    def _append_event(
        self,
        *,
        work: dict[str, Any],
        slice_id: str,
        event_type: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> None:
        append = getattr(self.service, "_append_assurance_event", None)
        baseline_for_slice = getattr(self.service, "_baseline_for_slice", None)
        if callable(append):
            append(
                work_id=work["entity_id"],
                subject_id=slice_id,
                event_type=event_type,
                actor_id=actor_id,
                baseline_id=(baseline_for_slice(slice_id) if callable(baseline_for_slice) else None),
                payload=payload,
            )
        refresh = getattr(self.service, "_refresh_work_view", None)
        if callable(refresh):
            refresh(work["entity_id"])

    def record_intent(
        self,
        *,
        slice_id: str,
        actor_id: str,
        turn_id: str,
        effect_key: str,
        action: str,
        target: str,
        payload_hash: str | None = None,
        expected_state: Any = None,
        idempotency_key: str | None = None,
        recovery_strategy: str = "RECONCILABLE",
        required_for_closure: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sl, work = self._require_turn(
            slice_id=slice_id,
            actor_id=actor_id,
            turn_id=turn_id,
            allowed_modes={"CONTINUE", "EXECUTE", "MODIFY", "CONTROL"},
        )
        if sl.get("closure_state") == "CLOSED":
            raise InvalidTransition("closed Slice cannot authorize a new external effect")

        effect_key = str(effect_key or "").strip()
        action = str(action or "").strip()
        target = str(target or "").strip()
        if not effect_key or not action or not target:
            raise ValueError("effect_key, action and target are required")

        def same_logical_effect(current: dict[str, Any]) -> bool:
            return (
                current.get("action") == action
                and current.get("target") == target
                and current.get("payload_hash") == payload_hash
                and current.get("expected_state") == expected_state
                and current.get("idempotency_key") == idempotency_key
            )

        existing = self.service.store.find(
            "effects", {"slice_id": slice_id, "effect_key": effect_key}
        )
        if existing:
            current = existing[0]
            if not same_logical_effect(current):
                raise InvalidTransition(
                    "EFFECT_KEY_CONFLICT: stable effect_key reused for a different logical effect"
                )
            return {"effect": current, "idempotent": True}

        now = utcnow()
        stable_id = "EFFECT-" + hashlib.sha256(
            f"{slice_id}\x1f{effect_key}".encode("utf-8")
        ).hexdigest()[:24].upper()
        doc = {
            **_base_doc(),
            "entity_id": stable_id,
            "effect_key": effect_key,
            "work_id": work["entity_id"],
            "family_id": sl["family_id"],
            "slice_id": slice_id,
            "turn_id": turn_id,
            "actor_id": actor_id,
            "action": action,
            "target": target,
            "payload_hash": payload_hash,
            "expected_state": expected_state,
            "observed_state": None,
            "idempotency_key": idempotency_key,
            "state": EffectState.AUTHORIZED.value,
            "outcome": EffectOutcome.UNKNOWN.value,
            "recovery_strategy": EffectRecoveryStrategy(str(recovery_strategy).upper()).value,
            "required_for_closure": bool(required_for_closure),
            "satisfied": None,
            "attempt_count": 0,
            "dispatch_history": [],
            "observation_history": [],
            "reconciliation_history": [],
            "authorized_at": now,
            "dispatched_at": None,
            "observed_at": None,
            "reconciled_at": None,
            "resolution": None,
            "metadata": dict(metadata or {}),
            "persistence_level": "CANONICAL",
        }
        try:
            saved = self.service.store.insert("effects", doc)
        except Exception:
            # Concurrent duplicate intent is still idempotent. The deterministic
            # entity id plus the Mongo compound unique index make this backend-neutral.
            raced = self.service.store.find(
                "effects", {"slice_id": slice_id, "effect_key": effect_key}
            )
            if raced and same_logical_effect(raced[0]):
                return {"effect": raced[0], "idempotent": True}
            raise
        self.service.link(
            from_type="SLICE",
            from_id=slice_id,
            relation="HAS_EFFECT",
            to_type="EFFECT",
            to_id=saved["entity_id"],
            source_actor_id=actor_id,
        )
        self._append_event(
            work=work,
            slice_id=slice_id,
            event_type="EFFECT_AUTHORIZED",
            actor_id=actor_id,
            payload={
                "effect_id": saved["entity_id"],
                "effect_key": effect_key,
                "action": action,
                "target": target,
            },
        )
        return {"effect": saved, "idempotent": False}

    def mark_dispatched(
        self,
        *,
        effect_id: str,
        actor_id: str,
        turn_id: str,
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        effect = self.service._must_get("effects", effect_id)
        _, work = self._require_turn(
            slice_id=effect["slice_id"],
            actor_id=actor_id,
            turn_id=turn_id,
            allowed_modes={"CONTINUE", "EXECUTE", "MODIFY", "CONTROL"},
        )
        state = str(effect.get("state") or "")
        outcome = str(effect.get("outcome") or EffectOutcome.UNKNOWN.value)
        if state == EffectState.RECONCILED.value:
            raise InvalidTransition("reconciled effect cannot be dispatched again")
        if state == EffectState.CANCELLED.value:
            raise InvalidTransition("cancelled effect cannot be dispatched")
        if state == EffectState.DISPATCHED.value:
            raise InvalidTransition(
                "OUTCOME_UNKNOWN_OBSERVE_BEFORE_RETRY: dispatched effect must be observed before redispatch"
            )
        if state == EffectState.OBSERVED.value and outcome not in {
            EffectOutcome.FAILED.value,
            EffectOutcome.NOT_EXECUTED.value,
        }:
            raise InvalidTransition(
                "RETRY_REQUIRES_KNOWN_NON_EXECUTION: UNKNOWN/PARTIAL/CONFIRMED effects must be reconciled, not blindly retried"
            )
        if state not in {EffectState.AUTHORIZED.value, EffectState.OBSERVED.value}:
            raise InvalidTransition(f"effect state {state!r} cannot dispatch")

        now = utcnow()
        attempt = int(effect.get("attempt_count") or 0) + 1
        history = list(effect.get("dispatch_history") or [])
        history.append(
            {
                "attempt": attempt,
                "dispatched_at": now,
                "receipt": dict(receipt or {}),
            }
        )
        updated = self.service._update(
            "effects",
            effect_id,
            {
                "state": EffectState.DISPATCHED.value,
                "outcome": EffectOutcome.UNKNOWN.value,
                "attempt_count": attempt,
                "dispatch_history": history,
                "dispatched_at": now,
                "updated_at": now,
            },
            expected_revision=int(effect.get("revision", 0)),
        )
        self._append_event(
            work=work,
            slice_id=effect["slice_id"],
            event_type="EFFECT_DISPATCHED",
            actor_id=actor_id,
            payload={"effect_id": effect_id, "attempt": attempt},
        )
        return updated

    def record_observation(
        self,
        *,
        effect_id: str,
        actor_id: str,
        turn_id: str,
        outcome: str,
        observed_state: Any = None,
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        effect = self.service._must_get("effects", effect_id)
        _, work = self._require_turn(
            slice_id=effect["slice_id"],
            actor_id=actor_id,
            turn_id=turn_id,
            allowed_modes={"CONTINUE", "EXECUTE", "VERIFY", "MODIFY", "CONTROL"},
        )
        state = effect.get("state")
        if state not in {
            EffectState.DISPATCHED.value,
            EffectState.OBSERVED.value,
            EffectState.RECONCILED.value,
        }:
            raise InvalidTransition("effect observation requires DISPATCHED, OBSERVED, or unresolved RECONCILED state")
        if state == EffectState.RECONCILED.value and effect.get("satisfied") is True:
            raise InvalidTransition("satisfied reconciled effect is terminal")

        normalized = EffectOutcome(str(outcome).upper())
        now = utcnow()
        history = list(effect.get("dispatch_history") or [])
        if receipt and history:
            history[-1] = {**history[-1], "observation_receipt": dict(receipt)}
        observations = list(effect.get("observation_history") or [])
        observations.append({
            "observed_at": now,
            "actor_id": actor_id,
            "outcome": normalized.value,
            "observed_state": observed_state,
            "receipt": dict(receipt or {}),
        })
        updated = self.service._update(
            "effects",
            effect_id,
            {
                "state": EffectState.OBSERVED.value,
                "outcome": normalized.value,
                "observed_state": observed_state,
                "observed_at": now,
                "dispatch_history": history,
                "observation_history": observations,
                "satisfied": None,
                "updated_at": now,
            },
            expected_revision=int(effect.get("revision", 0)),
        )
        self._append_event(
            work=work,
            slice_id=effect["slice_id"],
            event_type="EFFECT_OBSERVED",
            actor_id=actor_id,
            payload={"effect_id": effect_id, "outcome": normalized.value},
        )
        return updated

    def reconcile(
        self,
        *,
        effect_id: str,
        actor_id: str,
        turn_id: str,
        satisfied: bool,
        observed_state: Any = None,
        resolution: str | None = None,
        verifier_token: str | None = None,
    ) -> dict[str, Any]:
        effect = self.service._must_get("effects", effect_id)
        positive = bool(satisfied)
        _, work = self._require_turn(
            slice_id=effect["slice_id"],
            actor_id=actor_id,
            turn_id=turn_id,
            allowed_modes={"VERIFY"} if positive else {"EXECUTE", "VERIFY", "MODIFY", "CONTROL"},
        )
        if effect.get("state") != EffectState.OBSERVED.value:
            raise InvalidTransition("reconciliation requires an OBSERVED effect")
        if positive:
            if effect.get("outcome") != EffectOutcome.CONFIRMED.value:
                raise InvalidTransition(
                    "SATISFIED_RECONCILIATION_REQUIRES_CONFIRMED_OBSERVATION"
                )
            try:
                require_verifier(actor_id, verifier_token)
            except CapabilityDenied as exc:
                raise ApprovalRequired(str(exc)) from exc

        now = utcnow()
        reconciliations = list(effect.get("reconciliation_history") or [])
        reconciliations.append({
            "reconciled_at": now,
            "actor_id": actor_id,
            "satisfied": bool(satisfied),
            "observed_state": observed_state if observed_state is not None else effect.get("observed_state"),
            "resolution": resolution,
        })
        updated = self.service._update(
            "effects",
            effect_id,
            {
                "state": EffectState.RECONCILED.value,
                "satisfied": bool(satisfied),
                "observed_state": (
                    observed_state if observed_state is not None else effect.get("observed_state")
                ),
                "resolution": resolution,
                "reconciled_at": now,
                "reconciliation_history": reconciliations,
                "updated_at": now,
            },
            expected_revision=int(effect.get("revision", 0)),
        )
        self._append_event(
            work=work,
            slice_id=effect["slice_id"],
            event_type="EFFECT_RECONCILED",
            actor_id=actor_id,
            payload={
                "effect_id": effect_id,
                "satisfied": bool(satisfied),
                "resolution": resolution,
            },
        )
        return updated

    def status(
        self,
        *,
        slice_id: str | None = None,
        work_id: str | None = None,
        open_only: bool = False,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if slice_id:
            query["slice_id"] = slice_id
        if work_id:
            query["work_id"] = work_id
        rows = self.service.store.find("effects", query)
        if open_only:
            rows = [
                row
                for row in rows
                if not (
                    row.get("state") == EffectState.RECONCILED.value
                    and row.get("satisfied") is True
                )
            ]
        rows = sorted(rows, key=lambda row: str(row.get("created_at") or ""))
        return {"effects": rows, "count": len(rows), "open_only": bool(open_only)}

    def slice_closure_status(self, slice_id: str) -> dict[str, Any]:
        sl = self.service._must_get("slices", slice_id)
        blockers = unresolved_required_effects(self.service, slice_id)
        return {
            "slice_id": slice_id,
            "execution_state": sl.get("execution_state"),
            "validation_state": sl.get("validation_state"),
            "assurance_state": sl.get("assurance_state"),
            "closure_state": sl.get("closure_state"),
            "blocking_effect_ids": [row["entity_id"] for row in blockers],
            "closable": (
                sl.get("execution_state") == "DONE_CLAIMED"
                and sl.get("validation_state") == "VALIDATED"
                and sl.get("assurance_state") in {"VERIFIED", "ACCEPTED"}
                and not blockers
            ),
            "rule": (
                "WORKER_COMPLETION != SLICE_COMPLETION; required effects must be reconciled "
                "and satisfied before closure."
            ),
        }
