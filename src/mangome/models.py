from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .enums import (
    ApprovalStatus,
    AssuranceState,
    ClaimType,
    ContractKind,
    EdgeStatus,
    ExecutionState,
    SliceOrigin,
)
from .ids import new_id

SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseEntity(BaseModel):
    entity_id: str = Field(default_factory=new_id)
    schema_version: int = SCHEMA_VERSION
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class IntakeRequest(BaseEntity):
    request_text: str
    classification: str
    classification_source: str = "MANGOME_RULES"
    source_ref: str | None = None
    family_id: str | None = None


class Specification(BaseEntity):
    family_id: str
    contract_ids: list[str] = Field(default_factory=list)
    version: int = 1
    objective: str
    deliverables: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    supersedes_spec_id: str | None = None
    effective: bool = True


class Project(BaseEntity):
    project_key: str
    title: str
    description: str | None = None
    scope_ids: list[str] = Field(default_factory=list)
    family_ids: list[str] = Field(default_factory=list)
    last_activity_at: datetime = Field(default_factory=utcnow)


class FamilyCurrent(BaseModel):
    execution_state: ExecutionState = ExecutionState.PLANNED
    assurance_state: AssuranceState = AssuranceState.UNVERIFIED
    last_started_slice_id: str | None = None
    active_slice_ids: list[str] = Field(default_factory=list)
    last_done_claimed_slice_id: str | None = None
    last_verified_slice_id: str | None = None
    next_known_slice_ids: list[str] = Field(default_factory=list)
    active_actor_ids: list[str] = Field(default_factory=list)
    warning_flags: list[str] = Field(default_factory=list)
    last_timestamp: datetime = Field(default_factory=utcnow)


class Family(BaseEntity):
    family_key: str
    title: str
    project_ids: list[str] = Field(default_factory=list)
    scope_ids: list[str] = Field(default_factory=list)
    contract_ids: list[str] = Field(default_factory=list)
    slice_ids: list[str] = Field(default_factory=list)
    last_activity_at: datetime = Field(default_factory=utcnow)
    last_actor_id: str | None = None
    spec_ids: list[str] = Field(default_factory=list)
    current_spec_id: str | None = None
    current: FamilyCurrent = Field(default_factory=FamilyCurrent)


class StorageBinding(BaseModel):
    storage_system: str
    physical_location: str
    repository: str | None = None
    branch: str | None = None
    commit: str | None = None
    checksum: str | None = None
    persisted_at: datetime | None = None
    discovered_at: datetime = Field(default_factory=utcnow)


class ContractContribution(BaseEntity):
    declared_id: str
    family_id: str
    title: str
    kind: ContractKind = ContractKind.BASE
    artifact_ids: list[str] = Field(default_factory=list)
    storage_bindings: list[StorageBinding] = Field(default_factory=list)
    source_actor_id: str | None = None
    last_activity_at: datetime = Field(default_factory=utcnow)


class Gate(BaseModel):
    gate_id: str
    description: str
    status: Literal["OPEN", "PASS", "FAIL", "WAIVED"] = "OPEN"
    evidence_ids: list[str] = Field(default_factory=list)


class Slice(BaseEntity):
    declared_id: str
    family_id: str
    title: str
    objective: str | None = None
    contract_ids: list[str] = Field(default_factory=list)
    origin: SliceOrigin = SliceOrigin.PLANNED
    sequence: float | None = None
    parent_slice_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    execution_state: ExecutionState = ExecutionState.PLANNED
    assurance_state: AssuranceState = AssuranceState.UNVERIFIED
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    done_claimed_at: datetime | None = None
    verified_at: datetime | None = None
    accepted_at: datetime | None = None
    last_actor_id: str | None = None
    current_step: int | None = None
    total_steps: int | None = None
    gates: list[Gate] = Field(default_factory=list)
    blocker: str | None = None


class Estimate(BaseModel):
    effort: str | None = None
    duration_minutes: float | None = None
    cost: float | None = None
    currency: str = "EUR"
    tokens: int | None = None


class ProposedSlice(BaseModel):
    declared_id: str
    title: str
    objective: str | None = None
    sequence: float | None = None
    depends_on_declared_ids: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)


class Plan(BaseEntity):
    family_id: str
    request_id: str
    spec_id: str
    actor_id: str
    intent: str
    contract_ids: list[str] = Field(default_factory=list)
    proposed_slices: list[ProposedSlice] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    expected_scope: list[str] = Field(default_factory=list)
    estimate: Estimate = Field(default_factory=Estimate)
    acceptance_expectations: list[str] = Field(default_factory=list)
    status: Literal["RECORDED", "ACTIVE", "CLOSED", "SUPERSEDED", "CANCELLED"] = "RECORDED"


class Claim(BaseEntity):
    actor_id: str
    subject_id: str
    claim_type: ClaimType
    value: Any = None
    timestamp: datetime = Field(default_factory=utcnow)


class Evidence(BaseEntity):
    subject_id: str
    evidence_type: str
    source: str
    result: str | None = None
    artifact_id: str | None = None
    actor_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseEntity):
    logical_name: str
    artifact_type: str
    storage_system: str
    physical_location: str
    checksum: str | None = None
    exists: bool = True
    readable: bool = True
    writable: bool | None = None
    belongs_to: list[str] = Field(default_factory=list)
    last_seen_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseEntity):
    from_type: str
    from_id: str
    relation: str
    to_type: str
    to_id: str
    status: EdgeStatus = EdgeStatus.CONFIRMED
    source_artifact_id: str | None = None
    source_actor_id: str | None = None
    confidence: float | None = None


class Approval(BaseEntity):
    action_type: str
    subject_id: str
    requested_by: str
    reason: str
    status: ApprovalStatus = ApprovalStatus.REQUIRED
    decided_by: str | None = None
    decided_at: datetime | None = None


class CollisionWarning(BaseModel):
    family_overlap: bool = False
    artifact_overlap: list[str] = Field(default_factory=list)
    scope_overlap: list[str] = Field(default_factory=list)
    other_actor_ids: list[str] = Field(default_factory=list)
    other_plan_ids: list[str] = Field(default_factory=list)
    action: Literal["CONTINUE_ALLOWED"] = "CONTINUE_ALLOWED"


class FamilyStatusView(BaseModel):
    family_id: str
    family_key: str
    title: str
    execution_state: ExecutionState
    assurance_state: AssuranceState
    slice_counts: dict[str, int]
    active_slice_ids: list[str]
    last_started_slice_id: str | None
    last_done_claimed_slice_id: str | None
    last_verified_slice_id: str | None
    next_known_slice_ids: list[str]
    active_actor_ids: list[str]
    warnings: list[str]
    last_timestamp: datetime


class ModelProfile(BaseEntity):
    model_key: str
    provider: str | None = None
    access_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionReceipt(BaseEntity):
    family_id: str
    slice_id: str
    actor_id: str
    model_id: str | None = None
    work_class: str = "UNCLASSIFIED"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    execution_cost: float = 0.0
    verification_cost: float = 0.0
    repair_cost: float = 0.0
    human_cost: float = 0.0
    currency: str = "EUR"
    outcome: str = "UNKNOWN"
    context_tokens_raw: int | None = None
    context_tokens_compiled: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def durable_cost(self) -> float:
        return round(self.execution_cost + self.verification_cost + self.repair_cost + self.human_cost, 12)
