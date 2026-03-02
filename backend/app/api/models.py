"""Model management API endpoints."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from ..parsers.sysml_v2_parser import parse_sysml_v2
from ..parsers.reqif_parser import parse_reqif
from ..schemas.api import UploadResponse

router = APIRouter(prefix="/models", tags=["models"])

# In-memory model store
_models: dict = {}


def get_model(model_id: str):
    if model_id not in _models:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return _models[model_id]


def store_model(model):
    _models[model.model_id] = model


@router.post("/upload", response_model=UploadResponse)
async def upload_model(
    file: UploadFile = File(...),
    model_type: str = Form("auto"),
):
    """Upload and parse a model file."""
    content = await file.read()
    text = content.decode("utf-8")
    filename = file.filename or "unknown"

    # Auto-detect type
    if model_type == "auto":
        if filename.endswith(".sysml") or filename.endswith(".kerml"):
            model_type = "sysmlv2"
        elif filename.endswith(".reqif") or filename.endswith(".xml"):
            # Try to detect ReqIF by content
            if "<REQ-IF" in text or "<req-if" in text.lower():
                model_type = "reqif"
            else:
                model_type = "sysmlv2"  # default
        else:
            model_type = "sysmlv2"

    # Parse
    try:
        if model_type == "sysmlv2":
            parsed = parse_sysml_v2(text, filename)
        elif model_type == "reqif":
            parsed = parse_reqif(text, filename)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown model type: {model_type}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")

    store_model(parsed)
    data = parsed.to_dict()

    return UploadResponse(
        model_id=data["model_id"],
        filename=data["filename"],
        model_type=data["model_type"],
        summary=data["summary"],
        packages=data["packages"],
        elements=data["elements"],
    )


@router.get("/{model_id}")
async def get_model_detail(model_id: str):
    """Get a parsed model by ID."""
    model = get_model(model_id)
    return model.to_dict()


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    """Remove a model from memory."""
    if model_id in _models:
        del _models[model_id]
    return {"status": "deleted"}
