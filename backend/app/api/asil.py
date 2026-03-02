"""ASIL Assistant API endpoints."""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional

from ..models.safety import (
    SafetyProject, SafetyChain, Hazard, HazardousEvent,
    ASILDetermination, SafetyGoal, FSR, TestCase, FailureMode,
    ItemVersion, compute_asil,
    SEVERITY_DEFS, EXPOSURE_DEFS, CONTROLLABILITY_DEFS, ASIL_COLORS,
)
from ..parsers.safety_chain_parser import parse_safety_chain
from ..safety.ai_assistant import draft_item, revise_draft, suggest_asil_ratings
from ..analysis.safety_analysis import detect_gaps, compute_coverage, get_perspective
from ..export.reqif_export import export_to_reqif

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asil", tags=["asil"])

# ── In-memory storage ────────────────────────────────────────────
_projects: dict[str, SafetyProject] = {}

# ── Persistence directory ────────────────────────────────────────
DATA_DIR = Path(os.environ.get("MODELMERGE_DATA_DIR", "/tmp/modelmerge_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save_project(project: SafetyProject, username: str = "default"):
    """Persist project to JSON file."""
    path = DATA_DIR / f"{username}_project_{project.project_id}.json"
    path.write_text(json.dumps(project.to_dict(), indent=2))


def _load_projects(username: str = "default") -> list[SafetyProject]:
    """Load all projects for a user from disk."""
    projects = []
    for path in DATA_DIR.glob(f"{username}_project_*.json"):
        try:
            data = json.loads(path.read_text())
            # Reconstruct SafetyProject from dict (simplified — just store the dict)
            projects.append(data)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    return projects


# ── Request/Response Models ──────────────────────────────────────

class DraftRequest(BaseModel):
    chain_id: str
    level: str  # hazard, hazardous_event, safety_goal, fsr, test_case
    feedback: str = ""

class ReviseRequest(BaseModel):
    chain_id: str
    level: str
    instruction: str

class ApproveRequest(BaseModel):
    chain_id: str
    level: str
    name: str = ""
    text: str = ""
    # Extra fields for specific levels
    steps: str = ""
    expected_result: str = ""
    pass_criteria: str = ""
    safe_state: str = ""
    testable_criterion: str = ""
    operating_situation: str = ""

class RevertRequest(BaseModel):
    chain_id: str
    level: str
    version_idx: int

class ItemEditRequest(BaseModel):
    chain_id: str
    level: str
    name: str = ""
    description: str = ""
    # Optional extra fields
    steps: str = ""
    expected_result: str = ""
    pass_criteria: str = ""
    safe_state: str = ""
    testable_criterion: str = ""
    operating_situation: str = ""

class ASILDetermineRequest(BaseModel):
    chain_id: str
    severity: str = ""
    exposure: str = ""
    controllability: str = ""

class FailureModeRequest(BaseModel):
    name: str
    description: str = ""
    hazard_ids: list[str] = []

class SaveRequest(BaseModel):
    username: str = "default"
    password: str = ""

class LoginRequest(BaseModel):
    username: str = "default"
    password: str = ""


# ── Helper ───────────────────────────────────────────────────────

def _get_project(project_id: str | None = None) -> SafetyProject:
    """Get current project (uses most recent if no ID given)."""
    if project_id and project_id in _projects:
        return _projects[project_id]
    if _projects:
        return list(_projects.values())[-1]
    raise HTTPException(status_code=404, detail="No project loaded. Import a file first.")


def _get_chain(project: SafetyProject, chain_id: str) -> SafetyChain:
    for chain in project.chains:
        if chain.chain_id == chain_id:
            return chain
    raise HTTPException(status_code=404, detail=f"Chain {chain_id} not found")


def _get_chain_context(chain: SafetyChain) -> dict:
    """Build context dict for AI prompts — includes ALL chain info."""
    ctx = {}
    if chain.hazard and chain.hazard.status != "gap":
        ctx["hazard"] = f"{chain.hazard.name}: {chain.hazard.description}"
    if chain.hazardous_event and chain.hazardous_event.status != "gap":
        desc = chain.hazardous_event.description
        if chain.hazardous_event.operating_situation:
            desc += f" (Situation: {chain.hazardous_event.operating_situation})"
        ctx["hazardous_event"] = f"{chain.hazardous_event.name}: {desc}"
    if chain.asil_determination and chain.asil_determination.asil_level:
        ctx["asil_level"] = chain.asil_determination.asil_level
        if chain.asil_determination.severity:
            ctx["asil_detail"] = f"S={chain.asil_determination.severity}, E={chain.asil_determination.exposure}, C={chain.asil_determination.controllability}"
    if chain.safety_goal and chain.safety_goal.status != "gap":
        desc = chain.safety_goal.description
        if chain.safety_goal.safe_state:
            desc += f" (Safe state: {chain.safety_goal.safe_state})"
        ctx["safety_goal"] = f"{chain.safety_goal.name}: {desc}"
    if chain.fsr and chain.fsr.status != "gap":
        desc = chain.fsr.description
        if chain.fsr.testable_criterion:
            desc += f" (Testable criterion: {chain.fsr.testable_criterion})"
        ctx["fsr"] = f"{chain.fsr.name}: {desc}"
    if chain.test_case and chain.test_case.status != "gap":
        desc = chain.test_case.description
        if chain.test_case.steps:
            desc += f"\nSteps: {chain.test_case.steps}"
        if chain.test_case.expected_result:
            desc += f"\nExpected: {chain.test_case.expected_result}"
        ctx["test_case"] = f"{chain.test_case.name}: {desc}"
    return ctx


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/import")
async def import_safety_chain(file: UploadFile = File(...)):
    """Upload a file and extract safety chain items."""
    try:
        raw = (await file.read()).decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    filename = file.filename or "unknown"
    try:
        project = parse_safety_chain(raw, filename)
    except Exception as e:
        logger.error(f"Parse failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse: {e}")

    _projects[project.project_id] = project
    return project.to_dict()


@router.get("/project")
async def get_project(project_id: str = ""):
    """Get current project state."""
    project = _get_project(project_id or None)
    return project.to_dict()


@router.post("/chain/add")
async def add_chain(project_id: str = ""):
    """Add a new empty chain."""
    project = _get_project(project_id or None)
    chain = SafetyChain()
    chain.hazard = Hazard(status="gap")
    chain.hazardous_event = HazardousEvent(status="gap")
    chain.asil_determination = ASILDetermination()
    chain.safety_goal = SafetyGoal(status="gap")
    chain.fsr = FSR(status="gap")
    chain.test_case = TestCase(status="gap")
    project.chains.append(chain)
    return chain.to_dict()


@router.post("/draft")
async def draft_chain_item(req: DraftRequest):
    """AI drafts content for a gap in the chain."""
    project = _get_project()
    chain = _get_chain(project, req.chain_id)
    context = _get_chain_context(chain)

    # Get conversation history
    history_key = f"{req.chain_id}:{req.level}"
    history = project.draft_histories.get(history_key, [])

    result = await draft_item(
        level=req.level,
        chain_context=context,
        conversation_history=history,
        user_feedback=req.feedback,
    )

    # Store in history
    if req.feedback:
        history.append({"role": "user", "content": req.feedback})
    history.append({"role": "assistant", "content": result.get("text", "")})
    project.draft_histories[history_key] = history

    return result


@router.post("/revise")
async def revise_chain_item(req: ReviseRequest):
    """User asks AI to revise a draft."""
    project = _get_project()
    chain = _get_chain(project, req.chain_id)
    context = _get_chain_context(chain)

    # Get current text
    item = _get_item_from_chain(chain, req.level)
    current_text = item.description if item else ""

    history_key = f"{req.chain_id}:{req.level}"
    history = project.draft_histories.get(history_key, [])

    result = await revise_draft(
        current_text=current_text,
        user_instruction=req.instruction,
        level=req.level,
        chain_context=context,
        conversation_history=history,
    )

    # Update history
    history.append({"role": "user", "content": req.instruction})
    history.append({"role": "assistant", "content": result.get("text", "")})
    project.draft_histories[history_key] = history

    return result


@router.post("/approve")
async def approve_item(req: ApproveRequest):
    """User approves an item (creates a new version)."""
    project = _get_project()
    chain = _get_chain(project, req.chain_id)
    item = _get_item_from_chain(chain, req.level)

    if item is None:
        raise HTTPException(status_code=400, detail=f"No item at level {req.level}")

    # Create version snapshot
    version = ItemVersion(
        version=len(item.versions) + 1,
        text=req.text or item.description,
        name=req.name or item.name,
        author="user",
    )
    item.versions.append(version)

    # Update item
    if req.name:
        item.name = req.name
    if req.text:
        item.description = req.text
    item.status = "approved"
    item.approved = True

    # Apply extra fields per type
    if req.level == "test_case" and isinstance(item, TestCase):
        if req.steps:
            item.steps = req.steps
        if req.expected_result:
            item.expected_result = req.expected_result
        if req.pass_criteria:
            item.pass_criteria = req.pass_criteria
    elif req.level == "safety_goal" and isinstance(item, SafetyGoal):
        if req.safe_state:
            item.safe_state = req.safe_state
    elif req.level == "fsr" and isinstance(item, FSR):
        if req.testable_criterion:
            item.testable_criterion = req.testable_criterion
    elif req.level == "hazardous_event" and isinstance(item, HazardousEvent):
        if req.operating_situation:
            item.operating_situation = req.operating_situation

    return {"status": "approved", "item": _item_to_dict(item, req.level)}


@router.post("/revert")
async def revert_item(req: RevertRequest):
    """Revert an item to a previous version."""
    project = _get_project()
    chain = _get_chain(project, req.chain_id)
    item = _get_item_from_chain(chain, req.level)

    if not item or not item.versions:
        raise HTTPException(status_code=400, detail="No versions to revert to")

    if req.version_idx < 0 or req.version_idx >= len(item.versions):
        raise HTTPException(status_code=400, detail="Invalid version index")

    version = item.versions[req.version_idx]
    item.name = version.name
    item.description = version.text
    item.status = "draft"  # Revert removes approval
    item.approved = False

    return {"status": "reverted", "item": _item_to_dict(item, req.level)}


@router.put("/item")
async def edit_item(req: ItemEditRequest):
    """Manually edit any item."""
    project = _get_project()
    chain = _get_chain(project, req.chain_id)
    item = _get_item_from_chain(chain, req.level)

    if item is None:
        raise HTTPException(status_code=400, detail=f"No item at level {req.level}")

    if req.name:
        item.name = req.name
    if req.description:
        item.description = req.description

    # Mark as draft if it was a gap
    if item.status == "gap":
        item.status = "draft"

    # Apply extra fields
    if req.level == "test_case" and isinstance(item, TestCase):
        if req.steps:
            item.steps = req.steps
        if req.expected_result:
            item.expected_result = req.expected_result
    elif req.level == "safety_goal" and isinstance(item, SafetyGoal):
        if req.safe_state:
            item.safe_state = req.safe_state
    elif req.level == "fsr" and isinstance(item, FSR):
        if req.testable_criterion:
            item.testable_criterion = req.testable_criterion

    return {"status": "updated", "item": _item_to_dict(item, req.level)}


@router.get("/gaps")
async def list_gaps(project_id: str = ""):
    """List all gaps."""
    project = _get_project(project_id or None)
    return detect_gaps(project)


@router.get("/coverage")
async def get_coverage_metrics(project_id: str = ""):
    """Get coverage metrics."""
    project = _get_project(project_id or None)
    return compute_coverage(project)


@router.get("/perspective/{role}")
async def get_perspective_view(role: str, project_id: str = ""):
    """Get chains sorted by perspective."""
    project = _get_project(project_id or None)
    if role not in ("safety_engineer", "test_engineer", "req_engineer", "manager"):
        raise HTTPException(status_code=400, detail=f"Invalid perspective: {role}")
    return get_perspective(project, role)


@router.post("/asil-determine")
async def determine_asil(req: ASILDetermineRequest):
    """AI-assisted ASIL determination."""
    project = _get_project()
    chain = _get_chain(project, req.chain_id)

    # If no ratings provided, ask AI to suggest
    if not req.severity and not req.exposure and not req.controllability:
        hazard_desc = ""
        if chain.hazard and chain.hazard.description:
            hazard_desc = chain.hazard.description
        if not hazard_desc:
            return {"error": "No hazard description to analyze. Fill in the hazard first."}
        suggestion = await suggest_asil_ratings(hazard_desc)
        return {"suggestion": suggestion}

    # Compute ASIL from provided ratings
    asil_level = compute_asil(req.severity, req.exposure, req.controllability)

    if not chain.asil_determination:
        chain.asil_determination = ASILDetermination()

    chain.asil_determination.severity = req.severity
    chain.asil_determination.exposure = req.exposure
    chain.asil_determination.controllability = req.controllability
    chain.asil_determination.asil_level = asil_level

    # Propagate ASIL to safety goal and FSR
    if chain.safety_goal:
        chain.safety_goal.asil_level = asil_level
    if chain.fsr:
        chain.fsr.asil_level = asil_level

    return {
        "asil_level": asil_level,
        "determination": chain.asil_determination.to_dict(),
    }


@router.post("/asil-determine/approve")
async def approve_asil(req: ASILDetermineRequest):
    """Approve an ASIL determination with rationales."""
    project = _get_project()
    chain = _get_chain(project, req.chain_id)

    if not chain.asil_determination:
        raise HTTPException(status_code=400, detail="No ASIL determination to approve")

    chain.asil_determination.approved = True
    return {"status": "approved", "determination": chain.asil_determination.to_dict()}


@router.post("/failure-mode")
async def add_failure_mode(req: FailureModeRequest, project_id: str = ""):
    """Add a failure mode and link to hazards."""
    project = _get_project(project_id or None)
    fm = FailureMode(name=req.name, description=req.description, hazard_ids=req.hazard_ids)
    project.failure_modes.append(fm)

    # Link to hazards
    for chain in project.chains:
        if chain.hazard and chain.hazard.id in req.hazard_ids:
            chain.hazard.failure_mode_ids.append(fm.id)

    return fm.to_dict()


@router.post("/export/reqif")
async def export_reqif(project_id: str = ""):
    """Export project as ReqIF XML."""
    project = _get_project(project_id or None)
    xml_text = export_to_reqif(project)
    filename = f"{project.name or 'safety_chain'}_export.reqif"
    return PlainTextResponse(
        content=xml_text,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/definitions")
async def get_definitions():
    """Return ISO 26262 S/E/C definitions for the ASIL wizard."""
    return {
        "severity": SEVERITY_DEFS,
        "exposure": EXPOSURE_DEFS,
        "controllability": CONTROLLABILITY_DEFS,
        "asil_colors": ASIL_COLORS,
    }


# ── Data Persistence ─────────────────────────────────────────────

@router.post("/save")
async def save_data(req: SaveRequest):
    """Save all projects to disk under a username."""
    creds_path = DATA_DIR / "credentials.json"
    creds = {}
    if creds_path.exists():
        creds = json.loads(creds_path.read_text())

    # Store/verify credentials (simple plaintext — not secure, per user request)
    if req.username in creds:
        if creds[req.username] != req.password:
            raise HTTPException(status_code=403, detail="Wrong password")
    else:
        creds[req.username] = req.password
        creds_path.write_text(json.dumps(creds))

    # Save all projects
    for pid, project in _projects.items():
        _save_project(project, req.username)

    return {"status": "saved", "project_count": len(_projects)}


@router.post("/load")
async def load_data(req: LoginRequest):
    """Load saved projects for a username."""
    creds_path = DATA_DIR / "credentials.json"
    if creds_path.exists():
        creds = json.loads(creds_path.read_text())
        if req.username in creds and creds[req.username] != req.password:
            raise HTTPException(status_code=403, detail="Wrong password")

    saved = _load_projects(req.username)
    return {"projects": saved, "count": len(saved)}


# ── Helpers ──────────────────────────────────────────────────────

def _get_item_from_chain(chain: SafetyChain, level: str):
    """Get the item object from a chain by level name."""
    return {
        "hazard": chain.hazard,
        "hazardous_event": chain.hazardous_event,
        "safety_goal": chain.safety_goal,
        "fsr": chain.fsr,
        "test_case": chain.test_case,
    }.get(level)


def _item_to_dict(item, level: str) -> dict:
    """Convert item to dict."""
    if hasattr(item, 'to_dict'):
        return item.to_dict()
    return {"level": level, "status": "unknown"}
