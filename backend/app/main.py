"""ModelMerge API — FastAPI application."""
import os
import json
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .api.models import router as models_router
from .api.merge import router as merge_router
from .api.coverage import router as coverage_router
from .api.asil import router as asil_router
from .validation import compiler as compiler_module
from .safety import ai_assistant as ai_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ModelMerge API",
    description="Engineering model merge tool for SysML v2 and ReqIF",
    version="0.2.0",
)

# Allow the Vercel frontend + localhost for dev
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models_router, prefix="/api")
app.include_router(merge_router, prefix="/api")
app.include_router(coverage_router, prefix="/api")
app.include_router(asil_router, prefix="/api")

# ── API Key Persistence ──────────────────────────────────────────
DATA_DIR = Path(os.environ.get("MODELMERGE_DATA_DIR", "/tmp/modelmerge_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
API_KEY_FILE = DATA_DIR / "api_key.txt"


def _load_persisted_api_key():
    """Load API key from disk on startup."""
    if API_KEY_FILE.exists():
        key = API_KEY_FILE.read_text().strip()
        if key:
            compiler_module.ANTHROPIC_API_KEY = key
            ai_module.ANTHROPIC_API_KEY = key
            logger.info("Loaded persisted API key from disk")


# Load on startup
_load_persisted_api_key()


@app.get("/api/health")
async def health():
    has_api_key = bool(compiler_module.ANTHROPIC_API_KEY)
    return {
        "status": "ok",
        "service": "ModelMerge",
        "ai_validation": has_api_key,
    }


class ApiKeyRequest(BaseModel):
    api_key: str


@app.post("/api/config/api-key")
async def set_api_key(req: ApiKeyRequest):
    """Set the Anthropic API key at runtime and persist to disk."""
    compiler_module.ANTHROPIC_API_KEY = req.api_key
    ai_module.ANTHROPIC_API_KEY = req.api_key
    # Persist to disk so it survives refreshes / restarts
    try:
        API_KEY_FILE.write_text(req.api_key)
        logger.info("API key persisted to disk")
    except Exception as e:
        logger.warning(f"Failed to persist API key: {e}")
    return {"status": "ok", "ai_validation": True}


@app.get("/api/config/status")
async def config_status():
    """Check current configuration status."""
    has_api_key = bool(compiler_module.ANTHROPIC_API_KEY)
    has_java = compiler_module._find_java() is not None
    has_jar = __import__("os").path.exists(compiler_module.COMPILER_JAR)
    return {
        "ai_validation": has_api_key,
        "java_available": has_java,
        "compiler_jar": has_jar,
        "validation_method": "ai" if has_api_key else ("monticore" if has_java and has_jar else "semantic_only"),
    }
