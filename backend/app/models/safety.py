"""ISO 26262 Safety Chain data model with version history."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


# ── ASIL Lookup Matrix (ISO 26262 Part 3, Table 4) ──────────────

ASIL_MATRIX: dict[tuple[str, str, str], str] = {
    # (Severity, Exposure, Controllability) → ASIL
    ("S1", "E1", "C1"): "QM", ("S1", "E1", "C2"): "QM", ("S1", "E1", "C3"): "QM",
    ("S1", "E2", "C1"): "QM", ("S1", "E2", "C2"): "QM", ("S1", "E2", "C3"): "QM",
    ("S1", "E3", "C1"): "QM", ("S1", "E3", "C2"): "QM", ("S1", "E3", "C3"): "A",
    ("S1", "E4", "C1"): "QM", ("S1", "E4", "C2"): "A",  ("S1", "E4", "C3"): "B",

    ("S2", "E1", "C1"): "QM", ("S2", "E1", "C2"): "QM", ("S2", "E1", "C3"): "QM",
    ("S2", "E2", "C1"): "QM", ("S2", "E2", "C2"): "QM", ("S2", "E2", "C3"): "A",
    ("S2", "E3", "C1"): "QM", ("S2", "E3", "C2"): "A",  ("S2", "E3", "C3"): "B",
    ("S2", "E4", "C1"): "A",  ("S2", "E4", "C2"): "B",  ("S2", "E4", "C3"): "C",

    ("S3", "E1", "C1"): "QM", ("S3", "E1", "C2"): "QM", ("S3", "E1", "C3"): "A",
    ("S3", "E2", "C1"): "QM", ("S3", "E2", "C2"): "A",  ("S3", "E2", "C3"): "B",
    ("S3", "E3", "C1"): "A",  ("S3", "E3", "C2"): "B",  ("S3", "E3", "C3"): "C",
    ("S3", "E4", "C1"): "B",  ("S3", "E4", "C2"): "C",  ("S3", "E4", "C3"): "D",
}

# S0 always → QM, E0 always → QM, C0 always → QM
def compute_asil(severity: str, exposure: str, controllability: str) -> str:
    """Compute ASIL level from S/E/C ratings per ISO 26262."""
    if severity == "S0" or exposure == "E0" or controllability == "C0":
        return "QM"
    return ASIL_MATRIX.get((severity, exposure, controllability), "QM")


ASIL_COLORS = {"QM": "#94a3b8", "A": "#3b82f6", "B": "#f59e0b", "C": "#f97316", "D": "#ef4444"}

SEVERITY_DEFS = {
    "S0": "No injuries",
    "S1": "Light and moderate injuries",
    "S2": "Severe and life-threatening injuries (survival probable)",
    "S3": "Life-threatening injuries (survival uncertain), fatal injuries",
}
EXPOSURE_DEFS = {
    "E0": "Incredibly unlikely",
    "E1": "Very low probability (< 1% operating time)",
    "E2": "Low probability (1–10% operating time)",
    "E3": "Medium probability (10–50% operating time)",
    "E4": "High probability (> 50% operating time)",
}
CONTROLLABILITY_DEFS = {
    "C0": "Controllable in general",
    "C1": "Simply controllable (> 99% of drivers)",
    "C2": "Normally controllable (> 90% of drivers)",
    "C3": "Difficult to control or uncontrollable (< 90% of drivers)",
}


# ── Version Tracking ─────────────────────────────────────────────

@dataclass
class ItemVersion:
    """Snapshot of an item's text at a point in time."""
    version: int
    text: str
    name: str
    author: str = "user"  # "user" or "ai"
    timestamp: str = ""
    rationale: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "text": self.text,
            "name": self.name,
            "author": self.author,
            "timestamp": self.timestamp,
            "rationale": self.rationale,
        }


# ── Chain Items ──────────────────────────────────────────────────

@dataclass
class ASILDetermination:
    severity: str = ""       # S0–S3
    severity_rationale: str = ""
    exposure: str = ""       # E0–E4
    exposure_rationale: str = ""
    controllability: str = ""  # C0–C3
    controllability_rationale: str = ""
    asil_level: str = ""     # QM, A, B, C, D
    approved: bool = False

    def compute(self) -> str:
        if self.severity and self.exposure and self.controllability:
            self.asil_level = compute_asil(self.severity, self.exposure, self.controllability)
        return self.asil_level

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "severity_rationale": self.severity_rationale,
            "exposure": self.exposure,
            "exposure_rationale": self.exposure_rationale,
            "controllability": self.controllability,
            "controllability_rationale": self.controllability_rationale,
            "asil_level": self.asil_level,
            "approved": self.approved,
        }


@dataclass
class Hazard:
    id: str = ""
    name: str = ""
    description: str = ""
    failure_mode_ids: list[str] = field(default_factory=list)
    status: str = "gap"  # gap, draft, approved
    approved: bool = False
    versions: list[ItemVersion] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"HAZ-{uuid.uuid4().hex[:6].upper()}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "failure_mode_ids": self.failure_mode_ids,
            "status": self.status, "approved": self.approved,
            "versions": [v.to_dict() for v in self.versions],
        }


@dataclass
class HazardousEvent:
    id: str = ""
    hazard_id: str = ""
    name: str = ""
    description: str = ""
    operating_situation: str = ""
    status: str = "gap"
    approved: bool = False
    versions: list[ItemVersion] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"HE-{uuid.uuid4().hex[:6].upper()}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "hazard_id": self.hazard_id,
            "name": self.name, "description": self.description,
            "operating_situation": self.operating_situation,
            "status": self.status, "approved": self.approved,
            "versions": [v.to_dict() for v in self.versions],
        }


@dataclass
class SafetyGoal:
    id: str = ""
    hazard_id: str = ""
    name: str = ""
    description: str = ""
    asil_level: str = ""
    safe_state: str = ""
    status: str = "gap"
    approved: bool = False
    versions: list[ItemVersion] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"SG-{uuid.uuid4().hex[:6].upper()}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "hazard_id": self.hazard_id,
            "name": self.name, "description": self.description,
            "asil_level": self.asil_level, "safe_state": self.safe_state,
            "status": self.status, "approved": self.approved,
            "versions": [v.to_dict() for v in self.versions],
        }


@dataclass
class FSR:
    """Functional Safety Requirement."""
    id: str = ""
    safety_goal_id: str = ""
    name: str = ""
    description: str = ""
    testable_criterion: str = ""
    asil_level: str = ""
    status: str = "gap"   # gap, draft, review, approved
    approved: bool = False
    versions: list[ItemVersion] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"FSR-{uuid.uuid4().hex[:6].upper()}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "safety_goal_id": self.safety_goal_id,
            "name": self.name, "description": self.description,
            "testable_criterion": self.testable_criterion,
            "asil_level": self.asil_level,
            "status": self.status, "approved": self.approved,
            "versions": [v.to_dict() for v in self.versions],
        }


@dataclass
class TestCase:
    id: str = ""
    fsr_id: str = ""
    name: str = ""
    description: str = ""
    steps: str = ""
    expected_result: str = ""
    pass_criteria: str = ""
    status: str = "gap"
    approved: bool = False
    versions: list[ItemVersion] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"TC-{uuid.uuid4().hex[:6].upper()}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "fsr_id": self.fsr_id,
            "name": self.name, "description": self.description,
            "steps": self.steps, "expected_result": self.expected_result,
            "pass_criteria": self.pass_criteria,
            "status": self.status, "approved": self.approved,
            "versions": [v.to_dict() for v in self.versions],
        }


@dataclass
class FailureMode:
    """Lighter FMEA: just connects failure modes to hazards."""
    id: str = ""
    name: str = ""
    description: str = ""
    hazard_ids: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"FM-{uuid.uuid4().hex[:6].upper()}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "hazard_ids": self.hazard_ids,
        }


# ── Safety Chain (one traced path) ──────────────────────────────

@dataclass
class SafetyChain:
    """One full trace: Hazard → HazardousEvent → ASIL → SafetyGoal → FSR → TestCase."""
    chain_id: str = ""
    hazard: Optional[Hazard] = None
    hazardous_event: Optional[HazardousEvent] = None
    asil_determination: Optional[ASILDetermination] = None
    safety_goal: Optional[SafetyGoal] = None
    fsr: Optional[FSR] = None
    test_case: Optional[TestCase] = None

    def __post_init__(self):
        if not self.chain_id:
            self.chain_id = f"CHAIN-{uuid.uuid4().hex[:6].upper()}"

    @property
    def gap_count(self) -> int:
        count = 0
        for item in [self.hazard, self.hazardous_event, self.safety_goal, self.fsr, self.test_case]:
            if item is None or item.status == "gap":
                count += 1
        if self.asil_determination is None or not self.asil_determination.asil_level:
            count += 1
        return count

    @property
    def is_complete(self) -> bool:
        return self.gap_count == 0

    @property
    def approval_count(self) -> int:
        count = 0
        for item in [self.hazard, self.hazardous_event, self.safety_goal, self.fsr, self.test_case]:
            if item and item.approved:
                count += 1
        if self.asil_determination and self.asil_determination.approved:
            count += 1
        return count

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "hazard": self.hazard.to_dict() if self.hazard else None,
            "hazardous_event": self.hazardous_event.to_dict() if self.hazardous_event else None,
            "asil_determination": self.asil_determination.to_dict() if self.asil_determination else None,
            "safety_goal": self.safety_goal.to_dict() if self.safety_goal else None,
            "fsr": self.fsr.to_dict() if self.fsr else None,
            "test_case": self.test_case.to_dict() if self.test_case else None,
            "gap_count": self.gap_count,
            "is_complete": self.is_complete,
            "approval_count": self.approval_count,
        }


# ── Safety Project (top-level container) ────────────────────────

@dataclass
class SafetyProject:
    project_id: str = ""
    name: str = ""
    source_filename: str = ""
    chains: list[SafetyChain] = field(default_factory=list)
    failure_modes: list[FailureMode] = field(default_factory=list)
    # Draft conversation histories: {f"{chain_id}:{level}": [{role, text}]}
    draft_histories: dict = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.project_id:
            self.project_id = f"PROJ-{uuid.uuid4().hex[:6].upper()}"
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    @property
    def total_chains(self) -> int:
        return len(self.chains)

    @property
    def complete_chains(self) -> int:
        return sum(1 for c in self.chains if c.is_complete)

    @property
    def total_gaps(self) -> int:
        return sum(c.gap_count for c in self.chains)

    @property
    def coverage_pct(self) -> float:
        total_items = self.total_chains * 6  # 6 levels per chain
        if total_items == 0:
            return 0.0
        filled = total_items - self.total_gaps
        return round((filled / total_items) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "source_filename": self.source_filename,
            "chains": [c.to_dict() for c in self.chains],
            "failure_modes": [fm.to_dict() for fm in self.failure_modes],
            "total_chains": self.total_chains,
            "complete_chains": self.complete_chains,
            "total_gaps": self.total_gaps,
            "coverage_pct": self.coverage_pct,
            "created_at": self.created_at,
        }
