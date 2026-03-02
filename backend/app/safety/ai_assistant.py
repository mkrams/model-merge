"""AI-powered safety engineering assistant using Anthropic Claude API.

Drafts hazards, safety goals, FSRs, test cases. Helps with ASIL determination.
Supports iterative revision with conversation history.
Uses same httpx → Anthropic pattern as validation/compiler.py.
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
    api_key = ANTHROPIC_API_KEY
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY set — returning placeholder")
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
        # Extract text from response
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


# ── Drafting Functions ───────────────────────────────────────────

async def draft_item(
    level: str,
    chain_context: dict,
    conversation_history: list[dict] | None = None,
    user_feedback: str = "",
) -> dict:
    """Draft a safety chain item based on context.

    Args:
        level: 'hazard', 'hazardous_event', 'safety_goal', 'fsr', 'test_case'
        chain_context: Dict with info about the chain (what's filled upstream/downstream)
        conversation_history: Previous messages in this draft session
        user_feedback: Optional user instruction for revision

    Returns:
        dict with 'text', 'name', 'rationale'
    """
    prompts = {
        "hazard": _build_hazard_prompt(chain_context),
        "hazardous_event": _build_he_prompt(chain_context),
        "safety_goal": _build_sg_prompt(chain_context),
        "fsr": _build_fsr_prompt(chain_context),
        "test_case": _build_tc_prompt(chain_context),
    }

    prompt_text = prompts.get(level, f"Draft a {level} based on the given context.")

    messages = list(conversation_history or [])

    if user_feedback:
        messages.append({
            "role": "user",
            "content": f"Please revise the previous draft based on this feedback: {user_feedback}\n\nContext:\n{prompt_text}",
        })
    else:
        messages.append({
            "role": "user",
            "content": prompt_text,
        })

    response_text = await _call_claude(SAFETY_SYSTEM, messages)

    # Try to parse JSON if it looks like JSON
    try:
        result = json.loads(response_text)
        return {
            "text": result.get("description", result.get("text", response_text)),
            "name": result.get("name", ""),
            "rationale": result.get("rationale", ""),
            "steps": result.get("steps", ""),
            "expected_result": result.get("expected_result", ""),
            "pass_criteria": result.get("pass_criteria", ""),
        }
    except (json.JSONDecodeError, TypeError):
        # Plain text response
        return {
            "text": response_text,
            "name": "",
            "rationale": "",
        }


async def revise_draft(
    current_text: str,
    user_instruction: str,
    level: str,
    chain_context: dict,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Revise a draft based on user feedback."""
    messages = list(conversation_history or [])
    messages.append({
        "role": "user",
        "content": f"""Current draft for {level}:
\"{current_text}\"

User feedback: {user_instruction}

Context about the safety chain:
{_format_context(chain_context)}

Please provide a revised version. Respond with JSON:
{{"name": "short name", "description": "revised full text", "rationale": "why this revision"}}""",
    })

    response_text = await _call_claude(SAFETY_SYSTEM, messages)
    try:
        result = json.loads(response_text)
        return {
            "text": result.get("description", result.get("text", response_text)),
            "name": result.get("name", ""),
            "rationale": result.get("rationale", ""),
        }
    except (json.JSONDecodeError, TypeError):
        return {"text": response_text, "name": "", "rationale": ""}


async def suggest_asil_ratings(hazard_description: str) -> dict:
    """AI suggests S/E/C ratings with rationale for a hazard."""
    messages = [{
        "role": "user",
        "content": f"""Analyze this hazard and suggest ISO 26262 Severity, Exposure, and Controllability ratings:

Hazard: "{hazard_description}"

Respond with JSON:
{{
    "severity": "S0|S1|S2|S3",
    "severity_rationale": "explanation for severity rating",
    "exposure": "E0|E1|E2|E3|E4",
    "exposure_rationale": "explanation for exposure rating",
    "controllability": "C0|C1|C2|C3",
    "controllability_rationale": "explanation for controllability rating"
}}""",
    }]

    response_text = await _call_claude(ASIL_SYSTEM, messages)
    try:
        return json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return {
            "severity": "", "severity_rationale": response_text,
            "exposure": "", "exposure_rationale": "",
            "controllability": "", "controllability_rationale": "",
        }


# ── Prompt Builders ──────────────────────────────────────────────

def _format_context(ctx: dict) -> str:
    """Format chain context into readable text."""
    lines = []
    for key, val in ctx.items():
        if val and val != "gap":
            lines.append(f"- {key}: {val}")
    return "\n".join(lines) if lines else "No existing context."


def _build_hazard_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a hazard description for an ISO 26262 hazard analysis.

Existing context in this safety chain:
{context}

Respond with JSON:
{{"name": "short hazard name (e.g., 'Unintended acceleration')", "description": "2-3 sentence hazard description including the item, malfunctioning behavior, and potential consequence", "rationale": "why this hazard is relevant"}}"""


def _build_he_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a hazardous event description for an ISO 26262 hazard analysis.
A hazardous event combines a hazard with an operational situation.

Existing context in this safety chain:
{context}

Respond with JSON:
{{"name": "short hazardous event name", "description": "The hazardous event description combining the hazard with a specific driving scenario", "operating_situation": "the driving/operational situation", "rationale": "why this combination is realistic"}}"""


def _build_sg_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a safety goal for an ISO 26262 functional safety concept.
A safety goal is a top-level safety requirement assigned to a hazard, with an ASIL level.

Existing context in this safety chain:
{context}

Format: "The system shall [prevent/detect/mitigate] [hazardous behavior] to [avoid consequence]."

Respond with JSON:
{{"name": "short safety goal name (e.g., 'SG-01: Prevent unintended acceleration')", "description": "The safety goal text using shall-statement format", "safe_state": "the defined safe state", "rationale": "how this goal addresses the hazard"}}"""


def _build_fsr_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a Functional Safety Requirement (FSR) for an ISO 26262 safety concept.
An FSR is a testable requirement that implements a safety goal.

Existing context in this safety chain:
{context}

Requirements for a good FSR:
- Uses "shall" statement format
- Is measurable and testable
- Includes timing constraints where relevant
- Specifies fault detection/reaction behavior

Respond with JSON:
{{"name": "short FSR name (e.g., 'FSR-01: Torque monitoring')", "description": "The FSR text using shall-statement format", "testable_criterion": "how to verify this requirement", "rationale": "how this FSR implements the safety goal"}}"""


def _build_tc_prompt(ctx: dict) -> str:
    context = _format_context(ctx)
    return f"""Draft a test case to verify a Functional Safety Requirement.

Existing context in this safety chain:
{context}

Respond with JSON:
{{"name": "short test case name", "description": "test case objective", "steps": "1. [step]\\n2. [step]\\n3. [step]", "expected_result": "what should happen if the FSR is met", "pass_criteria": "measurable criteria for pass/fail"}}"""
