from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .ids import new_id
from .integrity import IntegrityMangoMeService
from .models import utcnow
from .schema import CURRENT_SCHEMA_VERSION
from .service import InvalidTransition, MangoMeError, RevisionConflict


TURN_MODES = {"QUERY", "CONTINUE", "EXECUTE", "VERIFY", "MODIFY", "CONTROL"}
_MUTATING_TURN_MODES = {"CONTINUE", "EXECUTE", "VERIFY", "MODIFY", "CONTROL"}


class TurnBindingError(MangoMeError):
    pass


class ContractGenerationConflict(MangoMeError):
    pass


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _base_doc() -> dict[str, Any]:
    now = utcnow()
    return {
        "entity_id": new_id(),
        "schema_version": CURRENT_SCHEMA_VERSION,
        "revision": 0,
        "created_at": now,
        "updated_at": now,
    }


class ContractGovernedMangoMeService(IntegrityMangoMeService):
    """Integrity service with contract-first turn binding and immutable contract generations.

    Existing MangoMe entities remain untouched. Contract generation state is kept in
    separate append-only collections so the hardening can be introduced without
    rewriting historical Contract, Specification, Plan or Slice documents.
    """

    def _resolve_contract(self, contract_ref: str) -> dict[str, Any]:
        direct = self.store.get("contracts", contract_ref)
        if direct is not None:
            return direct
        matches = self.store.find("contracts", {"declared_id": contract_ref})
        if not matches:
            raise KeyError(f"unknown contract {contract_ref}")
        if len(matches) != 1:
            raise TurnBindingError(
                f"contract reference {contract_ref!r} is ambiguous; use the canonical contract entity_id"
            )
        return matches[0]

    def _head(self, contract_id: str, *, create: bool = False) -> dict[str, Any] | None:
        rows = self.store.find("contract_heads", {"contract_id": contract_id})
        if rows:
            return rows[0]
        if not create:
            return None
        doc = {
            **_base_doc(),
            "contract_id": contract_id,
            "current_generation": 0,
            "current_generation_id": None,
            "current_content_hash": None,
            "active_grant_id": None,
        }
        try:
            return self.store.insert("contract_heads", doc)
        except Exception:
            # A concurrent creator may have won the unique contract_id race.
            rows = self.store.find("contract_heads", {"contract_id": contract_id})
            if rows:
                return rows[0]
            raise

    def _generation_by_id(self, generation_id: str | None) -> dict[str, Any] | None:
        if not generation_id:
            return None
        return self.store.get("contract_generations", generation_id)

    def contract_state(self, contract_ref: str, *, include_content: bool = False) -> dict[str, Any]:
        contract = self._resolve_contract(contract_ref)
        head = self._head(contract["entity_id"], create=False)
        current = self._generation_by_id((head or {}).get("current_generation_id"))
        generations = sorted(
            self.store.find("contract_generations", {"contract_id": contract["entity_id"]}),
            key=lambda row: int(row.get("generation", 0)),
        )
        generation_summaries = []
        for row in generations:
            item = {
                "entity_id": row.get("entity_id"),
                "generation": row.get("generation"),
                "content_hash": row.get("content_hash"),
                "previous_generation_id": row.get("previous_generation_id"),
                "previous_content_hash": row.get("previous_content_hash"),
                "change_type": row.get("change_type"),
                "promoted_by": row.get("promoted_by"),
                "turn_id": row.get("turn_id"),
                "promoted_at": row.get("promoted_at"),
                "source_binding": row.get("source_binding"),
                "status": row.get("status"),
            }
            if include_content:
                item["content"] = row.get("content")
            generation_summaries.append(item)
        current_summary = next(
            (item for item in generation_summaries if item.get("entity_id") == (head or {}).get("current_generation_id")),
            None,
        )
        return {
            "contract": contract,
            "canonical_content_present": current is not None,
            "current_generation": int((head or {}).get("current_generation", 0)),
            "current_generation_id": (head or {}).get("current_generation_id"),
            "current_content_hash": (head or {}).get("current_content_hash"),
            "active_generation_grant_id": (head or {}).get("active_grant_id"),
            "current": current_summary,
            "generations": generation_summaries,
            "storage_bindings": contract.get("storage_bindings") or [],
            "rule": (
                "Physical files are representations of this logical Contract. A changed local file is an observation, "
                "not a new canonical generation until the authorized MODIFY turn promotes it."
            ),
        }

    def _expire_grant_if_needed(self, head: dict[str, Any]) -> dict[str, Any]:
        grant_id = head.get("active_grant_id")
        if not grant_id:
            return head
        grant = self.store.get("contract_generation_grants", grant_id)
        if not grant or grant.get("status") != "ACTIVE":
            return self._update(
                "contract_heads",
                head["entity_id"],
                {"active_grant_id": None, "updated_at": utcnow()},
                expected_revision=int(head.get("revision", 0)),
            )
        expires_at = _utc_datetime(grant.get("expires_at"))
        if expires_at and expires_at <= utcnow():
            self._update(
                "contract_generation_grants",
                grant_id,
                {"status": "EXPIRED", "updated_at": utcnow()},
                expected_revision=int(grant.get("revision", 0)),
            )
            return self._update(
                "contract_heads",
                head["entity_id"],
                {"active_grant_id": None, "updated_at": utcnow()},
                expected_revision=int(head.get("revision", 0)),
            )
        return head

    def _acquire_generation_grant(
        self,
        *,
        contract: dict[str, Any],
        turn_id: str,
        actor_id: str,
        ttl_minutes: int,
    ) -> dict[str, Any]:
        if ttl_minutes < 1 or ttl_minutes > 1440:
            raise ValueError("ttl_minutes must be between 1 and 1440")
        head = self._head(contract["entity_id"], create=True)
        assert head is not None
        head = self._expire_grant_if_needed(head)
        existing_id = head.get("active_grant_id")
        if existing_id:
            existing = self.store.get("contract_generation_grants", existing_id)
            if existing and existing.get("status") == "ACTIVE":
                if existing.get("turn_id") == turn_id and existing.get("actor_id") == actor_id:
                    return existing
                raise ContractGenerationConflict(
                    "CONTRACT_GENERATION_WRITE_ALREADY_GRANTED: another bound turn owns the canonical promotion right"
                )

        now = utcnow()
        grant = {
            **_base_doc(),
            "contract_id": contract["entity_id"],
            "family_id": contract["family_id"],
            "turn_id": turn_id,
            "actor_id": actor_id,
            "base_generation": int(head.get("current_generation", 0)),
            "base_content_hash": head.get("current_content_hash"),
            "status": "ACTIVE",
            "expires_at": now + timedelta(minutes=ttl_minutes),
            "promoted_generation_id": None,
        }
        saved = self.store.insert("contract_generation_grants", grant)
        try:
            self._update(
                "contract_heads",
                head["entity_id"],
                {"active_grant_id": saved["entity_id"], "updated_at": now},
                expected_revision=int(head.get("revision", 0)),
            )
        except RevisionConflict as exc:
            current = self.store.get("contract_generation_grants", saved["entity_id"])
            if current:
                self._update(
                    "contract_generation_grants",
                    saved["entity_id"],
                    {"status": "CANCELLED", "updated_at": utcnow()},
                    expected_revision=int(current.get("revision", 0)),
                )
            raise ContractGenerationConflict(
                "CONTRACT_GENERATION_WRITE_RACE: another turn acquired the contract promotion right"
            ) from exc
        return saved

    def bind_turn(
        self,
        *,
        request_text: str,
        mode: str,
        actor_id: str,
        contract_ref: str,
        ttl_minutes: int = 240,
    ) -> dict[str, Any]:
        normalized_mode = mode.strip().upper()
        if normalized_mode not in TURN_MODES:
            raise TurnBindingError(f"unsupported turn mode {mode!r}; expected one of {sorted(TURN_MODES)}")
        contract = self._resolve_contract(contract_ref)
        turn = {
            **_base_doc(),
            "request_text": request_text,
            "mode": normalized_mode,
            "actor_id": actor_id,
            "contract_id": contract["entity_id"],
            "family_id": contract["family_id"],
            "status": "BOUND",
            "execution_authorized": normalized_mode in {"CONTINUE", "EXECUTE"},
            "verification_authorized": normalized_mode == "VERIFY",
            "normative_mutation_authorized": normalized_mode == "MODIFY",
            "control_authorized": normalized_mode == "CONTROL",
        }
        saved_turn = self.store.insert("turn_bindings", turn)
        grant = None
        if normalized_mode == "MODIFY":
            try:
                grant = self._acquire_generation_grant(
                    contract=contract,
                    turn_id=saved_turn["entity_id"],
                    actor_id=actor_id,
                    ttl_minutes=ttl_minutes,
                )
            except Exception:
                current_turn = self.store.get("turn_bindings", saved_turn["entity_id"])
                if current_turn and current_turn.get("status") == "BOUND":
                    self._update(
                        "turn_bindings",
                        saved_turn["entity_id"],
                        {"status": "DENIED", "updated_at": utcnow()},
                        expected_revision=int(current_turn.get("revision", 0)),
                    )
                raise
        family = self._must_get("families", contract["family_id"])
        current_spec = self.store.get("specs", family.get("current_spec_id")) if family.get("current_spec_id") else None
        effective_ids = set(self.effective_family_view(contract["family_id"]).get("effective_contract_ids") or [])
        return {
            "turn": saved_turn,
            "contract": self.contract_state(contract["entity_id"], include_content=False),
            "effective_spec": current_spec,
            "target_contract_is_effective": contract["entity_id"] in effective_ids,
            "generation_grant": grant,
            "allowed": {
                "read_contract_truth": True,
                "continue_or_execute_slices": normalized_mode in {"CONTINUE", "EXECUTE"},
                "submit_verification": normalized_mode == "VERIFY",
                "promote_contract_generation": normalized_mode == "MODIFY",
                "control": normalized_mode == "CONTROL",
            },
            "forbidden_inference": (
                "Recovered ACTIVE work, Plans or Slices are context only. They do not become the current user intent "
                "and do not authorize execution or contract mutation for this turn."
            ),
        }

    def release_contract_generation_grant(
        self,
        *,
        grant_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        grant = self._must_get("contract_generation_grants", grant_id)
        if grant.get("actor_id") != actor_id:
            raise TurnBindingError("only the actor owning the generation grant may release it")
        if grant.get("status") != "ACTIVE":
            return grant
        head = self._head(grant["contract_id"], create=False)
        now = utcnow()
        updated = self._update(
            "contract_generation_grants",
            grant_id,
            {"status": "RELEASED", "release_reason": reason, "updated_at": now},
            expected_revision=int(grant.get("revision", 0)),
        )
        if head and head.get("active_grant_id") == grant_id:
            self._update(
                "contract_heads",
                head["entity_id"],
                {"active_grant_id": None, "updated_at": now},
                expected_revision=int(head.get("revision", 0)),
            )
        turn = self.store.get("turn_bindings", grant.get("turn_id")) if grant.get("turn_id") else None
        if turn and turn.get("status") == "BOUND":
            try:
                self._update(
                    "turn_bindings",
                    turn["entity_id"],
                    {"status": "RELEASED", "updated_at": now},
                    expected_revision=int(turn.get("revision", 0)),
                )
            except RevisionConflict:
                pass
        return updated

    def promote_contract_generation(
        self,
        *,
        contract_ref: str,
        turn_id: str,
        grant_id: str,
        actor_id: str,
        content: str,
        change_type: str = "MODIFY",
        source_binding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        contract = self._resolve_contract(contract_ref)
        turn = self._must_get("turn_bindings", turn_id)
        if turn.get("status") != "BOUND" or turn.get("mode") != "MODIFY":
            raise TurnBindingError("CONTRACT_PROMOTION_REQUIRES_BOUND_MODIFY_TURN")
        if turn.get("actor_id") != actor_id or turn.get("contract_id") != contract["entity_id"]:
            raise TurnBindingError("turn actor/contract does not match contract promotion request")

        grant = self._must_get("contract_generation_grants", grant_id)
        if grant.get("status") != "ACTIVE":
            raise ContractGenerationConflict("contract generation grant is not ACTIVE")
        if grant.get("turn_id") != turn_id or grant.get("actor_id") != actor_id:
            raise ContractGenerationConflict("contract generation grant is bound to another turn/actor")
        if grant.get("contract_id") != contract["entity_id"]:
            raise ContractGenerationConflict("contract generation grant is bound to another contract")
        expires_at = _utc_datetime(grant.get("expires_at"))
        if expires_at and expires_at <= utcnow():
            raise ContractGenerationConflict("contract generation grant has expired")

        head = self._head(contract["entity_id"], create=True)
        assert head is not None
        if head.get("active_grant_id") != grant_id:
            raise ContractGenerationConflict("contract head is owned by another generation grant")
        if int(head.get("current_generation", 0)) != int(grant.get("base_generation", 0)):
            raise ContractGenerationConflict("CONTRACT_GENERATION_CONFLICT: canonical generation advanced")
        if head.get("current_content_hash") != grant.get("base_content_hash"):
            raise ContractGenerationConflict("CONTRACT_GENERATION_CONFLICT: canonical content hash changed")

        max_bytes = int(os.environ.get("MANGOME_CONTRACT_MAX_BYTES", str(8 * 1024 * 1024)))
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > max_bytes:
            raise ValueError(
                f"contract content exceeds MANGOME_CONTRACT_MAX_BYTES ({len(content_bytes)} > {max_bytes})"
            )
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        if head.get("current_content_hash") == content_hash:
            return {
                "promoted": False,
                "reason": "CONTRACT_CONTENT_UNCHANGED",
                "contract": self.contract_state(contract["entity_id"], include_content=False),
                "generation_grant": grant,
            }

        now = utcnow()
        generation = {
            **_base_doc(),
            "contract_id": contract["entity_id"],
            "family_id": contract["family_id"],
            "generation": int(head.get("current_generation", 0)) + 1,
            "content": content,
            "content_hash": content_hash,
            "previous_generation_id": head.get("current_generation_id"),
            "previous_content_hash": head.get("current_content_hash"),
            "change_type": change_type.strip().upper() or "MODIFY",
            "turn_id": turn_id,
            "grant_id": grant_id,
            "promoted_by": actor_id,
            "promoted_at": now,
            "source_binding": source_binding,
            "status": "PENDING",
        }
        saved_generation = self.store.insert("contract_generations", generation)
        try:
            updated_head = self._update(
                "contract_heads",
                head["entity_id"],
                {
                    "current_generation": saved_generation["generation"],
                    "current_generation_id": saved_generation["entity_id"],
                    "current_content_hash": content_hash,
                    "active_grant_id": None,
                    "updated_at": now,
                },
                expected_revision=int(head.get("revision", 0)),
            )
        except RevisionConflict as exc:
            current_generation = self.store.get("contract_generations", saved_generation["entity_id"])
            if current_generation:
                try:
                    self._update(
                        "contract_generations",
                        current_generation["entity_id"],
                        {"status": "CONFLICTED", "updated_at": utcnow()},
                        expected_revision=int(current_generation.get("revision", 0)),
                    )
                except RevisionConflict:
                    pass
            raise ContractGenerationConflict(
                "CONTRACT_GENERATION_CONFLICT: canonical head changed during promotion"
            ) from exc

        post_commit_warnings: list[str] = []
        current_generation = self.store.get("contract_generations", saved_generation["entity_id"])
        if current_generation:
            try:
                saved_generation = self._update(
                    "contract_generations",
                    current_generation["entity_id"],
                    {"status": "CANONICAL", "updated_at": utcnow()},
                    expected_revision=int(current_generation.get("revision", 0)),
                )
            except RevisionConflict:
                post_commit_warnings.append("GENERATION_STATUS_PROJECTION_CONFLICT")
        current_grant = self.store.get("contract_generation_grants", grant_id)
        if current_grant:
            try:
                self._update(
                    "contract_generation_grants",
                    grant_id,
                    {
                        "status": "CONSUMED",
                        "promoted_generation_id": saved_generation["entity_id"],
                        "updated_at": utcnow(),
                    },
                    expected_revision=int(current_grant.get("revision", 0)),
                )
            except RevisionConflict:
                post_commit_warnings.append("GENERATION_GRANT_PROJECTION_CONFLICT")
        current_turn = self.store.get("turn_bindings", turn_id)
        if current_turn:
            try:
                self._update(
                    "turn_bindings",
                    turn_id,
                    {"status": "COMPLETED", "updated_at": utcnow()},
                    expected_revision=int(current_turn.get("revision", 0)),
                )
            except RevisionConflict:
                post_commit_warnings.append("TURN_STATUS_PROJECTION_CONFLICT")
        latest_contract = self._must_get("contracts", contract["entity_id"])
        contract_patch: dict[str, Any] = {"last_activity_at": utcnow(), "updated_at": utcnow()}
        if source_binding and source_binding.get("physical_location"):
            bindings = list(latest_contract.get("storage_bindings") or [])
            key = (source_binding.get("storage_system"), source_binding.get("physical_location"))
            normalized_binding = dict(source_binding)
            normalized_binding["persisted_at"] = now
            normalized_binding.setdefault("discovered_at", now)
            replaced = False
            for index, existing in enumerate(bindings):
                if (existing.get("storage_system"), existing.get("physical_location")) == key:
                    bindings[index] = {**existing, **normalized_binding}
                    replaced = True
                    break
            if not replaced:
                bindings.append(normalized_binding)
            contract_patch["storage_bindings"] = bindings
        try:
            self._update(
                "contracts",
                contract["entity_id"],
                contract_patch,
                expected_revision=int(latest_contract.get("revision", 0)),
            )
        except RevisionConflict:
            # The canonical generation commit already succeeded. Physical binding metadata
            # is secondary and must never turn a successful generation promotion into a
            # false failure. A later reconciliation can refresh it.
            post_commit_warnings.append("CONTRACT_BINDING_PROJECTION_CONFLICT")
        return {
            "promoted": True,
            "generation": saved_generation,
            "head": updated_head,
            "contract": self.contract_state(contract["entity_id"], include_content=False),
            "warnings": post_commit_warnings,
        }

    def recovery_context(self, project_ref: str) -> dict[str, Any]:
        context = super().recovery_context(project_ref)
        for family in context.get("families") or []:
            family_id = family.get("family_id")
            contracts = self.store.find("contracts", {"family_id": family_id})
            effective_ids = set(self.effective_family_view(family_id).get("effective_contract_ids") or [])
            family["contract_truth"] = [
                {
                    **self.contract_state(contract["entity_id"], include_content=False),
                    "effective": contract["entity_id"] in effective_ids,
                }
                for contract in contracts
            ]
            family["execution_state_role"] = (
                "DERIVED_SUPPORTING_STATE: Plans/Slices help execute the unresolved contract/specification delta; "
                "they are not the primary recovered user intent."
            )
        context["recovery_priority"] = [
            "CURRENT_USER_TURN",
            "EFFECTIVE_CONTRACT_AND_SPECIFICATION",
            "OBSERVED_ARTIFACTS_AND_EVIDENCE",
            "DERIVED_PLAN_AND_SLICE_STATE",
        ]
        context["turn_policy"] = {
            "recovered_active_work_is_current_intent": False,
            "active_slice_grants_current_turn_execution": False,
            "bind_current_turn_to_contract_before_productive_work": True,
            "local_contract_change_is_canonical": False,
        }
        context["rule"] = (
            "Recovery is contract-first. Canonical Contract/Specification truth survives path changes and session loss. "
            "Recovered Plans/Slices are derived execution context only and never substitute for the current user's intent. "
            "Bind the current turn to the intended Contract before continuing, executing, verifying, modifying, or controlling work."
        )
        return context

    def session_restore(self, project_ref: str) -> dict[str, Any]:
        restored = super().session_restore(project_ref)
        if restored.get("restore_state") == "STATE_NOT_FOUND":
            restored["current_turn_execution_authorized"] = False
            restored["turn_binding_required"] = True
            return restored
        candidates = list(restored.get("next_executable_items") or [])
        restored["recovered_executable_items"] = candidates
        restored["productive_execution_allowed"] = False
        restored["current_turn_execution_authorized"] = False
        restored["turn_binding_required"] = True
        restored["execution_rule"] = (
            "RECOVERED_WORK_IS_CONTEXT_NOT_CURRENT_INTENT; bind the current user turn to the intended Contract. "
            "Only an explicit CONTINUE/EXECUTE turn may authorize productive execution; VERIFY and MODIFY remain separate modes."
        )
        return restored
