"""ModelMerge API — FastAPI application."""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .api.models import router as models_router
from .api.merge import router as merge_router
from .api.coverage import router as coverage_router
from .validation import compiler as compiler_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")

app = FastAPI(
    title="ModelMerge API",
    description="Engineering model merge tool for SysML v2 and ReqIF",
    version="0.1.0",
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
    """Set the Anthropic API key at runtime (stored in memory only)."""
    compiler_module.ANTHROPIC_API_KEY = req.api_key
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
