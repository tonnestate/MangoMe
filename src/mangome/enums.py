from enum import Enum

try:  # Python 3.11+
    from enum import StrEnum  # type: ignore
except ImportError:  # Python 3.10 compatibility
    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return self.value


class ContractKind(StrEnum):
    BASE = "BASE"
    ADDITION = "ADDITION"
    AMENDMENT = "AMENDMENT"
    EXTENSION = "EXTENSION"
    REPAIR = "REPAIR"
    RECOVERY = "RECOVERY"
    EVALUATION = "EVALUATION"
    VALIDATION = "VALIDATION"
    SPECIFICATION = "SPECIFICATION"
    OTHER = "OTHER"


class ExecutionState(StrEnum):
    PLANNED = "PLANNED"
    STARTED = "STARTED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    DONE_CLAIMED = "DONE_CLAIMED"
    CANCELLED = "CANCELLED"


class AssuranceState(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    PARTIAL = "PARTIAL"
    VERIFIED = "VERIFIED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class SliceOrigin(StrEnum):
    IMPORTED = "IMPORTED"
    PLANNED = "PLANNED"
    DISCOVERED = "DISCOVERED"
    DERIVED = "DERIVED"


class EdgeStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    SUGGESTED = "SUGGESTED"
    REJECTED = "REJECTED"


class RelationType(StrEnum):
    ADDS_TO = "ADDS_TO"
    AMENDS = "AMENDS"
    EXTENDS = "EXTENDS"
    REPAIRS = "REPAIRS"
    RECOVERS = "RECOVERS"
    SUPERSEDES = "SUPERSEDES"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    VALIDATES = "VALIDATES"
    IMPLEMENTS = "IMPLEMENTS"
    PART_OF = "PART_OF"
    EXPOSED_BY = "EXPOSED_BY"
    RELATES_TO = "RELATES_TO"


class EntityType(StrEnum):
    PROJECT = "PROJECT"
    FAMILY = "FAMILY"
    CONTRACT = "CONTRACT"
    SPEC = "SPEC"
    SLICE = "SLICE"
    PLAN = "PLAN"
    ARTIFACT = "ARTIFACT"
    EVIDENCE = "EVIDENCE"
    APPROVAL = "APPROVAL"
    MODEL = "MODEL"


class ClaimType(StrEnum):
    SLICE_STARTED = "SLICE_STARTED"
    WORK_COMPLETED = "WORK_COMPLETED"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    TEST_PASSED = "TEST_PASSED"
    TEST_FAILED = "TEST_FAILED"
    OTHER = "OTHER"


class ApprovalStatus(StrEnum):
    REQUIRED = "REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EvidenceClass(StrEnum):
    CLAIM = "CLAIM"
    TEST_RESULT = "TEST_RESULT"
    RUNTIME_OBSERVATION = "RUNTIME_OBSERVATION"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    ARTIFACT_CHECK = "ARTIFACT_CHECK"
    HUMAN_ATTESTATION = "HUMAN_ATTESTATION"
    EXTERNAL_REVIEW = "EXTERNAL_REVIEW"
    OTHER = "OTHER"


class EvidenceTrust(StrEnum):
    UNATTESTED = "UNATTESTED"
    VERIFIER_ATTESTED = "VERIFIER_ATTESTED"
    OWNER_ATTESTED = "OWNER_ATTESTED"


class EvidenceVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"


class DependencyLevel(StrEnum):
    DONE_CLAIMED = "DONE_CLAIMED"
    VERIFIED = "VERIFIED"
    ACCEPTED = "ACCEPTED"
