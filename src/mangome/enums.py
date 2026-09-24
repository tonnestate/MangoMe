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
