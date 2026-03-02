"""ASIL API endpoints for graph-based safety model."""
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
    SafetyProject, SafetyItem, TraceLink, ItemType, LinkType, compute_asil,
    SEVERITY_DEFS, EXPOSURE_DEFS, CONTROLLABILITY_DEFS, ASIL_COLORS,
)
from ..parsers.safety_chain_parser import parse_safety_chain, parse_safety_chain_bytes
from ..safety.ai_assistant import draft_item, revise_draft, suggest_asil_ratings
from ..analysis.safety_analysis import detect_gaps, compute_coverage, get_perspective, get_trace_tree, get_trace_matrix
from ..export.reqif_export import export_to_reqif

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asil", tags=["asil"])

# ── In-memory storage ────────────────────────────────────────────
_current_project: Optional[SafetyProject] = None

# ── Persistence directory ────────────────────────────────────────
DATA_DIR = Path(os.environ.get("MODELMERGE_DATA_DIR", "/tmp/modelmerge_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Request/Response Models ──────────────────────────────────────

class ImportRequest(BaseModel):
    pass


class ItemCreateRequest(BaseModel):
    item_type: str
    name: str = ""
    description: str = ""
    attributes: dict = {}


class ItemUpdateRequest(BaseModel):
    name: str = ""
    description: str = ""
    status: str = ""
    attributes: dict = {}


class LinkCreateRequest(BaseModel):
    source_id: str
    target_id: str
    rationale: str = ""


class ApproveRequest(BaseModel):
    item_id: str
    name: str = ""
    description: str = ""
    attributes: dict = {}


class DraftRequest(BaseModel):
    item_id: str
    feedback: str = ""


class ReviseRequest(BaseModel):
    item_id: str
    instruction: str


class ASILDetermineRequest(BaseModel):
    item_id: str
    severity: str = ""
    exposure: str = ""
    controllability: str = ""


class SaveRequest(BaseModel):
    username: str = "default"


class LoadRequest(BaseModel):
    username: str = "default"


# ── Helpers ──────────────────────────────────────────────────────

def _get_project() -> SafetyProject:
    """Get current project."""
    global _current_project
    if _current_project is None:
        raise HTTPException(status_code=404, detail="No project loaded. Import a file first.")
    return _current_project


def _save_project(project: SafetyProject, username: str = "default"):
    """Persist project to JSON file."""
    path = DATA_DIR / f"{username}_project_{project.project_id}.json"
    path.write_text(json.dumps(project.to_dict(), indent=2))


def _load_project(username: str = "default") -> Optional[SafetyProject]:
    """Load first project for a user from disk."""
    for path in DATA_DIR.glob(f"{username}_project_*.json"):
        try:
            data = json.loads(path.read_text())
            # Reconstruct SafetyProject from dict
            project = _project_from_dict(data)
            return project
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    return None


def _project_from_dict(data: dict) -> SafetyProject:
    """Reconstruct SafetyProject from dict."""
    project = SafetyProject(
        project_id=data.get("project_id", ""),
        name=data.get("name", ""),
        created_at=data.get("created_at", ""),
    )

    # Reconstruct items
    for item_data in data.get("items", []):
        item_type_str = item_data.get("item_type", "fsr")
        try:
            item_type = ItemType(item_type_str)
        except ValueError:
            item_type = ItemType.FSR

        item = SafetyItem(
            item_id=item_data.get("item_id", ""),
            item_type=item_type,
            name=item_data.get("name", ""),
            description=item_data.get("description", ""),
            status=item_data.get("status", "gap"),
            attributes=item_data.get("attributes", {}),
        )
        project.items.append(item)

    # Reconstruct links
    for link_data in data.get("links", []):
        link_type_str = link_data.get("link_type", "hazard_to_event")
        try:
            link_type = LinkType(link_type_str)
        except ValueError:
            link_type = LinkType.HAZARD_TO_EVENT

        link = TraceLink(
            link_id=link_data.get("link_id", ""),
            source_id=link_data.get("source_id", ""),
            target_id=link_data.get("target_id", ""),
            link_type=link_type,
            rationale=link_data.get("rationale", ""),
        )
        project.links.append(link)

    return project


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/import")
async def import_safety_chain(file: UploadFile = File(...)):
    """Upload a file and parse into graph model.

    Supports: .csv, .xlsx, .xls, .docx
    """
    global _current_project
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    filename = file.filename or "unknown"
    try:
        project = parse_safety_chain_bytes(file_bytes, filename)
    except Exception as e:
        logger.error(f"Parse failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse: {e}")

    _current_project = project
    return project.to_dict()


@router.get("/project")
async def get_project():
    """Get current project state."""
    project = _get_project()
    return project.to_dict()


@router.get("/item/{item_id}")
async def get_item(item_id: str):
    """Get single item with its links."""
    project = _get_project()
    item = project.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    result = item.to_dict()
    result["parents"] = [p.to_dict() for p in project.get_parents(item_id)]
    result["children"] = [c.to_dict() for c in project.get_children(item_id)]
    return result


@router.post("/item")
async def create_item(req: ItemCreateRequest):
    """Create new item."""
    project = _get_project()

    try:
        item_type = ItemType(req.item_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid item type: {req.item_type}")

    item = SafetyItem(
        item_type=item_type,
        name=req.name,
        description=req.description,
        status="draft",
        attributes=req.attributes or {},
    )
    project.add_item(item)
    return item.to_dict()


@router.put("/item/{item_id}")
async def update_item(item_id: str, req: ItemUpdateRequest):
    """Update item fields."""
    project = _get_project()
    item = project.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    if req.name:
        item.name = req.name
    if req.description:
        item.description = req.description
    if req.status:
        item.status = req.status
    if req.attributes:
        item.attributes.update(req.attributes)

    return item.to_dict()


@router.delete("/item/{item_id}")
async def delete_item(item_id: str):
    """Delete item and its links."""
    project = _get_project()
    project.remove_item(item_id)
    return {"status": "deleted", "item_id": item_id}


@router.post("/item/{item_id}/approve")
async def approve_item(item_id: str, req: ApproveRequest):
    """Approve item."""
    project = _get_project()
    item = project.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    if req.name:
        item.name = req.name
    if req.description:
        item.description = req.description
    if req.attributes:
        item.attributes.update(req.attributes)

    item.status = "approved"
    return item.to_dict()


@router.post("/item/{item_id}/revert")
async def revert_item(item_id: str, version: int = 0):
    """Revert to version (stub — versions not fully implemented in graph model)."""
    project = _get_project()
    item = project.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    item.status = "draft"
    return item.to_dict()


@router.post("/link")
async def create_link(req: LinkCreateRequest):
    """Create link between items."""
    project = _get_project()

    source = project.get_item(req.source_id)
    target = project.get_item(req.target_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Source or target item not found")

    # Auto-detect link type
    link_type = _infer_link_type(source.item_type, target.item_type)
    if not link_type:
        raise HTTPException(status_code=400, detail=f"Cannot link {source.item_type.value} to {target.item_type.value}")

    link = project.add_link(req.source_id, req.target_id, link_type, req.rationale)
    return link.to_dict()


def _infer_link_type(source_type: ItemType, target_type: ItemType) -> Optional[LinkType]:
    """Infer link type between two item types."""
    source_str = source_type.value if hasattr(source_type, 'value') else source_type
    target_str = target_type.value if hasattr(target_type, 'value') else target_type
    key = (source_str, target_str)

    type_map = {
        ("hazard", "hazardous_event"): LinkType.HAZARD_TO_EVENT,
        ("hazardous_event", "safety_goal"): LinkType.EVENT_TO_GOAL,
        ("safety_goal", "fsr"): LinkType.GOAL_TO_FSR,
        ("fsr", "tsr"): LinkType.FSR_TO_TSR,
        ("tsr", "verification"): LinkType.TSR_TO_VERIFICATION,
        ("fsr", "verification"): LinkType.FSR_TO_VERIFICATION,
    }
    return type_map.get(key)


@router.delete("/link/{link_id}")
async def delete_link(link_id: str):
    """Delete link."""
    project = _get_project()
    project.remove_link(link_id)
    return {"status": "deleted", "link_id": link_id}


@router.post("/item/{item_id}/draft")
async def draft_item_endpoint(item_id: str, req: DraftRequest):
    """AI draft for item."""
    project = _get_project()
    item = project.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    # Build context from parents and children
    context = {
        "parents": [p.to_dict() for p in project.get_parents(item_id)],
        "children": [c.to_dict() for c in project.get_children(item_id)],
        "item_type": item.item_type.value if hasattr(item.item_type, 'value') else item.item_type,
    }

    result = await draft_item(
        item_type=context["item_type"],
        context=context,
        user_feedback=req.feedback,
    )
    return result


@router.post("/item/{item_id}/revise")
async def revise_item_endpoint(item_id: str, req: ReviseRequest):
    """AI revise item."""
    project = _get_project()
    item = project.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    context = {
        "parents": [p.to_dict() for p in project.get_parents(item_id)],
        "children": [c.to_dict() for c in project.get_children(item_id)],
        "item_type": item.item_type.value if hasattr(item.item_type, 'value') else item.item_type,
    }

    result = await revise_draft(
        item_type=context["item_type"],
        current_text=item.description,
        user_instruction=req.instruction,
        context=context,
    )
    return result


@router.post("/asil-determine")
async def determine_asil(req: ASILDetermineRequest):
    """AI-assisted ASIL determination."""
    project = _get_project()
    item = project.get_item(req.item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {req.item_id} not found")

    if not req.severity or not req.exposure or not req.controllability:
        # Ask AI to suggest
        if not item.description:
            return {"error": "No item description to analyze. Fill in the item first."}
        suggestion = await suggest_asil_ratings(item.description)
        return {"suggestion": suggestion}

    # Compute ASIL from ratings
    asil_level = compute_asil(req.severity, req.exposure, req.controllability)
    item.attributes["asil_level"] = asil_level
    item.attributes["severity"] = req.severity
    item.attributes["exposure"] = req.exposure
    item.attributes["controllability"] = req.controllability

    return {
        "item_id": req.item_id,
        "asil_level": asil_level,
        "severity": req.severity,
        "exposure": req.exposure,
        "controllability": req.controllability,
    }


@router.get("/gaps")
async def list_gaps():
    """List all gaps."""
    project = _get_project()
    return detect_gaps(project)


@router.get("/coverage")
async def get_coverage_metrics():
    """Get coverage metrics."""
    project = _get_project()
    return compute_coverage(project)


@router.get("/perspective/{role}")
async def get_perspective_view(role: str):
    """Get items sorted by perspective."""
    project = _get_project()
    if role not in ("safety_engineer", "test_engineer", "req_engineer", "manager"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    return get_perspective(project, role)


@router.get("/trace/{item_id}")
async def get_trace(item_id: str):
    """Get full trace tree for item."""
    project = _get_project()
    return get_trace_tree(project, item_id)


@router.get("/matrix/{source_type}/{target_type}")
async def get_matrix(source_type: str, target_type: str):
    """Get traceability matrix between two item types."""
    project = _get_project()
    return get_trace_matrix(project, source_type, target_type)


@router.post("/export/reqif")
async def export_reqif_endpoint():
    """Export project as ReqIF XML."""
    project = _get_project()
    xml_text = export_to_reqif(project)
    filename = f"{project.name or 'safety_project'}_export.reqif"
    return PlainTextResponse(
        content=xml_text,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/save")
async def save_data(req: SaveRequest):
    """Save project to disk."""
    project = _get_project()
    _save_project(project, req.username)
    return {"status": "saved", "project_id": project.project_id}


@router.post("/load")
async def load_data(req: LoadRequest):
    """Load project from disk."""
    global _current_project
    project = _load_project(req.username)
    if not project:
        raise HTTPException(status_code=404, detail=f"No project found for user {req.username}")
    _current_project = project
    return {"projects": [project.to_dict()], "count": 1}


@router.get("/definitions")
async def get_definitions():
    """Return ISO 26262 S/E/C definitions."""
    return {
        "severity": SEVERITY_DEFS,
        "exposure": EXPOSURE_DEFS,
        "controllability": CONTROLLABILITY_DEFS,
        "asil_colors": ASIL_COLORS,
    }
