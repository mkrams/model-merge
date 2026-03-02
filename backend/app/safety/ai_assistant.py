"""AI-powered safety engineering assistant using Anthropic Claude API.

Works with graph-based model: drafts items with parent/child context.
"""
from __future__ import annotations
import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"


async def _call_claude(system_prompt: str, messages: list[dict], max_tokens: int = 1500) -> str:
    """Call Anthropic API and return text response."""
    api_key = ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY set")
        return "[AI unavailable — set ANTHROPIC_API_KEY to enable AI drafting]"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": messages,
                },
                timeout=60.0,
            )
        response.raise_for_status()
        data = response.json()
        for block in data.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        return ""
    except Exception as e:
        logger.error(f"Claude API call failed: {e}", exc_info=True)
        return f"[AI error: {str(e)}]"


# ── System Prompts ───────────────────────────────────────────────

SAFETY_SYSTEM = """You are an expert ISO 26262 functional safety engineer.
You help draft safety artifacts that are precise, measurable, and compliant
with automotive safety standards. Your language is professional and technical.
When drafting, follow ISO 26262 conventions and use clear, unambiguous language.
Always respond with ONLY the requested content — no preamble, no explanation."""

ASIL_SYSTEM = """You are an expert in ISO 26262 hazard analysis and risk assessment.
You help determine ASIL levels by evaluating Severity, Exposure, and Controllability.
You provide clear rationale for each rating based on the hazard context.
Respond in JSON format when asked for structured output."""


# ── JSON Extraction Helper ───────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    """Try to extract JSON from response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[start:end]).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None


# ── Drafting Functions ───────────────────────────────────────────

async def draft_item(
    item_type: str,
    context: dict | None = None,
    conversation_history: list[dict] | None = None,
    user_feedback: str = "",
) -> dict:
    """Draft a safety item based on context.

    Args:
        item_type: 'hazard', 'hazardous_event', 'safety_goal', 'fsr', 'tsr', 'verification'
        context: Dict with parents, children, and other graph context
        conversation_history: Previous messages
        user_feedback: Optional user instruction

    Returns:
        dict with 'text', 'name', and type-specific fields
    """
    if context is None:
        context = {}

    prompts = {
        "hazard": _build_hazard_prompt(context),
        "hazardous_event": _build_he_prompt(context),
        "safety_goal": _build_sg_prompt(context),
        "fsr": _build_fsr_prompt(context),
        "tsr": _build_tsr_prompt(context),
        "verification": _build_verification_prompt(context),
    }

    prompt_text = prompts.get(item_type, f"Draft a {item_type}.")

    messages = list(conversation_history or [])

    if user_feedback:
        messages.append({
            "role": "user",
            "content": f"Please revise based on: {user_feedback}\n\nContext:\n{prompt_text}",
        })
    else:
        messages.append({
            "role": "user",
            "content": prompt_text,
        })

    response_text = await _call_claude(SAFETY_SYSTEM, messages)
    result = _extract_json(response_text)

    if result:
        return {
            "text": result.get("description", result.get("text", response_text)),
            "name": result.get("name", ""),
            "rationale": result.get("rationale", ""),
            "steps": result.get("steps", ""),
            "expected_result": result.get("expected_result", ""),
            "pass_criteria": result.get("pass_criteria", ""),
            "safe_state": result.get("safe_state", ""),
            "testable_criterion": result.get("testable_criterion", ""),
            "operating_situation": result.get("operating_situation", ""),
            "allocated_to": result.get("allocated_to", ""),
        }

    return {
        "text": response_text,
        "name": "",
        "rationale": "",
    }


async def revise_draft(
    item_type: str,
    current_text: str,
    user_instruction: str,
    context: dict | None = None,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Revise a draft based on user feedback."""
    if context is None:
        context = {}

    messages = list(conversation_history or [])

    # Build field list based on type
    fields = '"name": "short name", "description": "revised full text", "rationale": "why"'
    if item_type == "verification":
        fields += ', "method": "test|analysis|review", "steps": "...", "expected_result": "...", "pass_criteria": "..."'
    elif item_type == "safety_goal":
        fields += ', "safe_state": "the safe state"'
    elif item_type == "fsr":
        fields += ', "testable_criterion": "how to verify"'
    elif item_type == "tsr":
        fields += ', "allocated_to": "component", "testable_criterion": "how to verify"'
    elif item_type == "hazardous_event":
        fields += ', "operating_situation": "driving scenario"'

    messages.append({
        "role": "user",
        "content": f"""Current draft for {item_type}:
\"{current_text}\"

User feedback: {user_instruction}

Context:
{_format_context(context)}

Please provide revised version. Respond with JSON:
{{{fields}}}""",
    })

    response_text = await _call_claude(SAFETY_SYSTEM, messages)
    result = _extract_json(response_text)

    if result:
        return {
            "text": result.get("description", result.get("text", response_text)),
            "name": result.get("name", ""),
            "rationale": result.get("rationale", ""),
            "steps": result.get("steps", ""),
            "expected_result": result.get("expected_result", ""),
            "pass_criteria": result.get("pass_criteria", ""),
            "safe_state": result.get("safe_state", ""),
            "testable_criterion": result.get("testable_criterion", ""),
            "operating_situation": result.get("operating_situation", ""),
            "allocated_to": result.get("allocated_to", ""),
        }

    return {"text": response_text, "name": "", "rationale": ""}


async def suggest_asil_ratings(hazard_description: str) -> dict:
    """AI suggests S/E/C ratings with rationale."""
    messages = [{
        "role": "user",
        "content": f"""Analyze this hazard and suggest ISO 26262 S/E/C ratings:

Hazard: "{hazard_description}"

Respond with JSON:
{{
    "severity": "S0|S1|S2|S3",
    "severity_rationale": "explanation",
    "exposure": "E0|E1|E2|E3|E4",
    "exposure_rationale": "explanation",
    "controllability": "C0|C1|C2|C3",
    "controllability_rationale": "explanation"
}}""",
    }]

    response_text = await _call_claude(ASIL_SYSTEM, messages)
    result = _extract_json(response_text)
    if result:
        return result
    return {
        "severity": "", "severity_rationale": response_text,
        "exposure": "", "exposure_rationale": "",
        "controllability": "", "controllability_rationale": "",
    }


# ── Prompt Builders ──────────────────────────────────────────────

def _format_context(ctx: dict) -> str:
    """Format context into readable text."""
    lines = []
    if ctx.get("parents"):
        lines.append("Parents:")
        for parent in ctx["parents"]:
            lines.append(f"  - {parent.get('name', parent.get('item_id', 'unknown'))}: {parent.get('description', '')[:100]}")
    if ctx.get("children"):
        lines.append("Children:")
        for child in ctx["children"]:
            lines.append(f"  - {child.get('name', child.get('item_id', 'unknown'))}: {child.get('description', '')[:100]}")
    return "\n".join(lines) if lines else "No context."


def _build_hazard_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a hazard for ISO 26262 hazard analysis.

Context:
{context}

Respond with JSON:
{{"name": "short name (e.g., 'Unintended acceleration')", "description": "hazard description (item, malfunction, consequence)", "rationale": "why this hazard is relevant"}}"""


def _build_he_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a hazardous event: hazard + operational situation.

Context:
{context}

Respond with JSON:
{{"name": "short name", "description": "event description", "operating_situation": "driving scenario", "rationale": "relevance"}}"""


def _build_sg_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a safety goal (top-level requirement with ASIL).

Format: "The system shall [prevent/detect/mitigate] [behavior]..."

Context:
{context}

Respond with JSON:
{{"name": "short name", "description": "safety goal text (shall-statement)", "safe_state": "safe state definition", "rationale": "how it addresses the hazard"}}"""


def _build_fsr_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a Functional Safety Requirement (FSR): testable requirement implementing safety goal.

Must be measurable, include timing, specify fault detection.

Context:
{context}

Respond with JSON:
{{"name": "short name", "description": "FSR text (shall-statement)", "testable_criterion": "how to verify", "rationale": "how it implements the goal"}}"""


def _build_tsr_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a Technical Safety Requirement (TSR): component-level requirement.

Context:
{context}

Respond with JSON:
{{"name": "short name", "description": "TSR text", "allocated_to": "component/system", "testable_criterion": "verification method", "rationale": "mapping from FSR"}}"""


def _build_verification_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a verification method: test, analysis, or review to verify FSR/TSR.

Context:
{context}

Respond with JSON:
{{"name": "short name", "description": "verification objective", "method": "test|analysis|review", "steps": "1. step\\n2. step", "expected_result": "expected outcome", "pass_criteria": "measurable pass/fail"}}"""
