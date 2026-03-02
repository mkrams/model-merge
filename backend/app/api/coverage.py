"""Coverage analysis API endpoints."""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File

from ..parsers.sysml_v2_parser import parse_sysml_v2
from ..parsers.reqif_parser import parse_reqif
from ..analysis.coverage import analyze_coverage
from .models import get_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/coverage/upload")
async def coverage_from_upload(file: UploadFile = File(...)):
    """
    Upload a SysML v2 or ReqIF file and run coverage analysis.
    Returns coverage metrics, orphan requirements, compliance checks, etc.
    """
    try:
        raw = (await file.read()).decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    filename = file.filename or "unknown"

    # Detect file type and parse
    try:
        if filename.endswith(".reqif") or filename.endswith(".xml"):
            model = parse_reqif(raw, filename)
        else:
            model = parse_sysml_v2(raw, filename)
    except Exception as e:
        logger.error(f"Parse failed for coverage analysis: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse model: {str(e)}")

    # Run coverage analysis
    try:
        result = analyze_coverage(model)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Coverage analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Coverage analysis failed: {str(e)}")


@router.post("/coverage/{model_id}")
async def coverage_from_model(model_id: str):
    """
    Run coverage analysis on an already-uploaded model (by ID).
    """
    model = get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    try:
        result = analyze_coverage(model)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Coverage analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Coverage analysis failed: {str(e)}")
