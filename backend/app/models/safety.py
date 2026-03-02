"""ISO 26262 graph-based traceability model with many-to-many relationships."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import uuid
from datetime import datetime


class ItemType(str, Enum):
    """Item types in the safety traceability hierarchy."""
    HAZARD = "hazard"
    HAZARDOUS_EVENT = "hazardous_event"
    SAFETY_GOAL = "safety_goal"
    FSR = "fsr"
    TSR = "tsr"
    VERIFICATION = "verification"


class VerificationMethod(str, Enum):
    """Verification method types."""
    TEST = "test"
    ANALYSIS = "analysis"
    REVIEW = "review"


class LinkType(str, Enum):
    """Types of links in the traceability graph."""
    HAZARD_TO_EVENT = "hazard_to_event"
    EVENT_TO_GOAL = "event_to_goal"
    GOAL_TO_FSR = "goal_to_fsr"
    FSR_TO_TSR = "fsr_to_tsr"
    TSR_TO_VERIFICATION = "tsr_to_verification"
    FSR_TO_VERIFICATION = "fsr_to_verification"


# Valid link types between item types
VALID_LINKS: dict[tuple[str, str], LinkType] = {
    ("hazard", "hazardous_event"): LinkType.HAZARD_TO_EVENT,
    ("hazardous_event", "safety_goal"): LinkType.EVENT_TO_GOAL,
    ("safety_goal", "fsr"): LinkType.GOAL_TO_FSR,
    ("fsr", "tsr"): LinkType.FSR_TO_TSR,
    ("tsr", "verification"): LinkType.TSR_TO_VERIFICATION,
    ("fsr", "verification"): LinkType.FSR_TO_VERIFICATION,
}


@dataclass
class ItemVersion:
    """Snapshot of an item at a point in time."""
    version: int
    text: str
    author: str = "user"
    timestamp: str = ""
    fields: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "text": self.text,
            "author": self.author,
            "timestamp": self.timestamp,
            "fields": self.fields,
        }


@dataclass
class SafetyItem:
    """Universal item in the traceability graph.

    Type-specific attributes are stored in the attributes dict:
    - hazardous_event: severity, exposure, controllability, asil_level, operating_situation
    - safety_goal: safe_state
    - fsr: testable_criterion
    - tsr: allocated_to, testable_criterion
    - verification: method (test/analysis/review), steps, expected_result, pass_criteria
    """
    item_id: str = ""
    item_type: ItemType = ItemType.HAZARD
    name: str = ""
    description: str = ""
    status: str = "gap"
    versions: list = field(default_factory=list)
    attributes: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.item_id:
            self.item_id = f"{self.item_type.value}-{uuid.uuid4().hex[:8]}"
        # Ensure attributes is a dict
        if not isinstance(self.attributes, dict):
            self.attributes = {}

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type.value if isinstance(self.item_type, ItemType) else self.item_type,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "attributes": self.attributes,
            "versions": [v.to_dict() for v in self.versions],
        }


@dataclass
class TraceLink:
    """A directed link between two items in the traceability graph."""
    link_id: str = ""
    source_id: str = ""
    target_id: str = ""
    link_type: LinkType = LinkType.HAZARD_TO_EVENT
    rationale: str = ""

    def __post_init__(self):
        if not self.link_id:
            self.link_id = f"link-{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> dict:
        return {
            "link_id": self.link_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "link_type": self.link_type.value if isinstance(self.link_type, LinkType) else self.link_type,
            "rationale": self.rationale,
        }


@dataclass
class SafetyProject:
    """Top-level container: items + links form the traceability graph."""
    project_id: str = ""
    name: str = ""
    items: list = field(default_factory=list)
    links: list = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.project_id:
            self.project_id = f"proj-{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def get_item(self, item_id: str) -> Optional[SafetyItem]:
        """Get an item by ID."""
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None

    def get_items_by_type(self, item_type: ItemType) -> list:
        """Get all items of a specific type."""
        type_str = item_type.value if isinstance(item_type, ItemType) else item_type
        return [i for i in self.items if (i.item_type.value if isinstance(i.item_type, ItemType) else i.item_type) == type_str]

    def get_children(self, item_id: str) -> list:
        """Get all items that this item links TO (downstream)."""
        child_ids = [l.target_id for l in self.links if l.source_id == item_id]
        return [i for i in self.items if i.item_id in child_ids]

    def get_parents(self, item_id: str) -> list:
        """Get all items that link TO this item (upstream)."""
        parent_ids = [l.source_id for l in self.links if l.target_id == item_id]
        return [i for i in self.items if i.item_id in parent_ids]

    def get_links_from(self, item_id: str) -> list:
        """Get all links originating from an item."""
        return [l for l in self.links if l.source_id == item_id]

    def get_links_to(self, item_id: str) -> list:
        """Get all links targeting an item."""
        return [l for l in self.links if l.target_id == item_id]

    def add_item(self, item: SafetyItem) -> SafetyItem:
        """Add an item to the project."""
        self.items.append(item)
        return item

    def add_link(self, source_id: str, target_id: str, link_type: LinkType, rationale: str = "") -> TraceLink:
        """Add a link between two items."""
        link = TraceLink(source_id=source_id, target_id=target_id, link_type=link_type, rationale=rationale)
        self.links.append(link)
        return link

    def remove_link(self, link_id: str):
        """Remove a link by ID."""
        self.links = [l for l in self.links if l.link_id != link_id]

    def remove_item(self, item_id: str):
        """Remove an item and all its associated links."""
        self.items = [i for i in self.items if i.item_id != item_id]
        self.links = [l for l in self.links if l.source_id != item_id and l.target_id != item_id]

    def to_dict(self) -> dict:
        """Convert project to dictionary."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "items": [i.to_dict() for i in self.items],
            "links": [l.to_dict() for l in self.links],
            "created_at": self.created_at,
        }


# ASIL lookup matrix per ISO 26262 Part 3, Table 4
ASIL_MATRIX = {
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


def compute_asil(severity: str, exposure: str, controllability: str) -> str:
    """Compute ASIL level from S/E/C ratings per ISO 26262."""
    if severity == "S0" or exposure == "E0" or controllability == "C0":
        return "QM"
    key = (severity.upper(), exposure.upper(), controllability.upper())
    return ASIL_MATRIX.get(key, "QM")


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
