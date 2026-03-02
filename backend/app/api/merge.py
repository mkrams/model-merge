"""Merge workflow API endpoints."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
import uuid

from ..schemas.api import (
    MergeAnalyzeRequest, MergeApplyRequest, MergeApplyResponse,
    MergeDecision, ValidationResponse,
)
from ..merge.detector import analyze_merge
from ..merge.engine import apply_merge, generate_sysml_v2
from ..validation.semantic import validate_semantic
from ..validation.compiler import validate_with_compiler
from .models import get_model, store_model

router = APIRouter(prefix="/merge", tags=["merge"])

# In-memory merge store
_analyses: dict = {}
_merged_models: dict = {}


@router.post("/analyze")
async def analyze(req: MergeAnalyzeRequest):
    """Compare two models and return conflict analysis."""
    model_a = get_model(req.model_a_id)
    model_b = get_model(req.model_b_id)

    data_a = model_a.to_dict()
    data_b = model_b.to_dict()

    merge_id = str(uuid.uuid4())[:8]

    analysis = analyze_merge(
        elements_a=data_a["elements"],
        elements_b=data_b["elements"],
        model_a_id=req.model_a_id,
        model_b_id=req.model_b_id,
        model_a_name=model_a.filename,
        model_b_name=model_b.filename,
        merge_id=merge_id,
    )

    _analyses[merge_id] = {
        "analysis": analysis,
        "model_a_id": req.model_a_id,
        "model_b_id": req.model_b_id,
    }

    return analysis.to_dict()


@router.post("/apply", response_model=MergeApplyResponse)
async def apply(req: MergeApplyRequest):
    """Apply merge decisions and produce merged model."""
    if req.merge_id not in _analyses:
        raise HTTPException(status_code=404, detail=f"Merge analysis {req.merge_id} not found")

    merge_data = _analyses[req.merge_id]
    analysis = merge_data["analysis"]

    model_a = get_model(merge_data["model_a_id"])
    model_b = get_model(merge_data["model_b_id"])

    # Convert decisions list to dict
    decisions = {d.conflict_id: d.resolution for d in req.decisions}

    # Apply merge
    merged = apply_merge(model_a, model_b, analysis, decisions)

    # Generate text
    sysml_text = generate_sysml_v2(merged)

    # Store merged model
    store_model(merged)
    _merged_models[req.merge_id] = merged.model_id

    data = merged.to_dict()
    return MergeApplyResponse(
        merged_model_id=merged.model_id,
        filename=merged.filename,
        summary=data["summary"],
        packages=data["packages"],
        elements=data["elements"],
        sysml_text=sysml_text,
    )


@router.post("/{merge_id}/validate", response_model=ValidationResponse)
async def validate(merge_id: str):
    """Validate a merged model."""
    if merge_id not in _merged_models:
        raise HTTPException(status_code=404, detail=f"No merged model for merge {merge_id}")

    model = get_model(_merged_models[merge_id])

    # Semantic validation
    semantic_result = validate_semantic(model)

    # Generate text for compiler
    sysml_text = generate_sysml_v2(model)

    # Compiler validation
    compiler_result = validate_with_compiler(sysml_text)

    return ValidationResponse(
        semantic=semantic_result.to_dict(),
        compiler=compiler_result.to_dict(),
    )


@router.get("/{merge_id}/download")
async def download(merge_id: str, format: str = "sysmlv2"):
    """Download merged model as text file."""
    if merge_id not in _merged_models:
        raise HTTPException(status_code=404, detail=f"No merged model for merge {merge_id}")

    model = get_model(_merged_models[merge_id])
    text = generate_sysml_v2(model)

    return PlainTextResponse(
        content=text,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={model.filename}",
        },
    )
