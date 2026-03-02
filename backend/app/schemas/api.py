"""Pydantic models for API request/response schemas."""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class UploadResponse(BaseModel):
    model_id: str
    filename: str
    model_type: str
    summary: dict
    packages: list[dict]
    elements: list[dict]


class MergeAnalyzeRequest(BaseModel):
    model_a_id: str
    model_b_id: str


class MergeDecision(BaseModel):
    conflict_id: str
    resolution: str  # "keep_left", "keep_right", "merge_both"


class MergeApplyRequest(BaseModel):
    merge_id: str
    decisions: list[MergeDecision]


class MergeApplyResponse(BaseModel):
    merged_model_id: str
    filename: str
    summary: dict
    packages: list[dict]
    elements: list[dict]
    sysml_text: str


class ValidationResponse(BaseModel):
    semantic: dict
    compiler: dict
