"""
SysML v2 validation using AI (Anthropic Claude API) and optional MontiCore JAR fallback.

The AI validator sends the merged SysML v2 text to Claude and gets back structured
validation results — syntax errors, semantic issues, missing imports, type mismatches,
and suggestions for fixes. Uses direct HTTP calls (httpx) — no extra packages needed.
"""
from __future__ import annotations
import os
import json
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from .semantic import ValidationResult

logger = logging.getLogger(__name__)

# API key from env
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Optional: MontiCore JAR fallback
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_JAR = _BACKEND_DIR / "MCSysMLv2.jar"
COMPILER_JAR = os.environ.get("SYSML_COMPILER_JAR", str(_DEFAULT_JAR))
JAVA_PATH = os.environ.get("JAVA_PATH", "java")


VALIDATION_PROMPT = """You are a SysML v2 syntax and semantics validator. Your job is to analyze the following SysML v2 model text and identify any issues.

Check for:
1. **Syntax errors**: Invalid keywords, missing semicolons, unmatched braces, malformed declarations
2. **Import issues**: Imports that reference packages not defined in this file (note which are likely standard library: ScalarValues, Quantities, MeasurementReferences, ISQ, SI, ScalarFunctions, RequirementDerivation)
3. **Type reference errors**: Parts or ports referencing types that aren't defined or imported
4. **Semantic issues**: Duplicate names in the same scope, circular references, invalid multiplicity, malformed constraints
5. **Port/interface consistency**: Flow directions matching, interface ends connecting compatible ports
6. **Requirement issues**: Missing constraint expressions, unreferenced subjects

Return your analysis as a JSON object with this exact structure:
{
  "is_valid": true/false,
  "errors": ["list of error strings with line references where possible"],
  "warnings": ["list of warning strings"],
  "suggestions": ["list of improvement suggestions"]
}

Only flag real issues. Standard library imports (ISQ, SI, ScalarValues, Quantities, etc.) should NOT be flagged as errors — they are valid external dependencies. Be precise about line numbers when possible.

Here is the SysML v2 model to validate:

```sysml
%MODEL_TEXT%
```

Return ONLY the JSON object, no other text."""


def validate_with_compiler(sysml_text: str) -> ValidationResult:
    """
    Validate SysML v2 text. Tries AI validation first, falls back to MontiCore JAR.
    """
    logger.info(f"validate_with_compiler called. API key set: {bool(ANTHROPIC_API_KEY)}, key prefix: {ANTHROPIC_API_KEY[:10]}..." if ANTHROPIC_API_KEY else "validate_with_compiler called. No API key set.")

    # Try AI validation first
    if ANTHROPIC_API_KEY:
        logger.info("Using AI validation (Claude API)")
        return _validate_with_ai(sysml_text)

    # Fall back to MontiCore JAR
    logger.info("No API key — trying MontiCore JAR fallback")
    jar_result = _validate_with_monticore(sysml_text)
    if jar_result.source != "compiler_unavailable":
        return jar_result

    # Nothing available
    logger.warning("No validator configured")
    result = ValidationResult(source="compiler_unavailable")
    result.warnings.append(
        "No validator configured. Set ANTHROPIC_API_KEY for AI-powered validation, "
        "or install Java 11+ with MCSysMLv2.jar for compiler validation."
    )
    return result


def _validate_with_ai(sysml_text: str) -> ValidationResult:
    """Validate using Anthropic Claude API via direct HTTP (no extra packages needed)."""
    import httpx

    result = ValidationResult(source="ai_validator")

    logger.info("Starting AI validation with Claude API...")

    try:
        # Add line numbers for reference
        numbered_lines = []
        for i, line in enumerate(sysml_text.split("\n"), 1):
            numbered_lines.append(f"{i:4d} | {line}")
        numbered_text = "\n".join(numbered_lines)

        prompt = VALIDATION_PROMPT.replace("%MODEL_TEXT%", numbered_text)

        # Direct HTTP call to Anthropic API — no anthropic package needed
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60.0,
        )

        if response.status_code != 200:
            error_body = response.text
            logger.error(f"Anthropic API error {response.status_code}: {error_body}")

            if response.status_code == 401:
                result.warnings.append(
                    "Invalid API key. Check your key at https://console.anthropic.com"
                )
                result.source = "compiler_unavailable"
                return result
            elif response.status_code == 429:
                result.is_valid = False
                result.errors.append("Rate limited by Anthropic API. Try again in a moment.")
                return result
            else:
                result.is_valid = False
                result.errors.append(f"Anthropic API returned {response.status_code}: {error_body[:300]}")
                return result

        api_response = response.json()
        response_text = api_response["content"][0]["text"].strip()

        logger.info(f"AI response received ({len(response_text)} chars)")

        # Parse JSON from response (handle markdown code blocks)
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            response_text = response_text.rsplit("```", 1)[0]
        response_text = response_text.strip()

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response_text[start:end])
            else:
                logger.error(f"AI returned non-JSON: {response_text[:500]}")
                result.warnings.append("AI validator returned non-JSON response")
                result.warnings.append(f"Response preview: {response_text[:200]}")
                return result

        result.is_valid = data.get("is_valid", True)
        result.errors = data.get("errors", [])
        result.warnings = data.get("warnings", [])

        # Add suggestions as warnings
        suggestions = data.get("suggestions", [])
        for s in suggestions:
            result.warnings.append(f"Suggestion: {s}")

        if result.is_valid and not result.errors:
            result.warnings.insert(0, "AI validation passed: model appears syntactically and semantically valid")

        logger.info(f"AI validation complete — valid={result.is_valid}, errors={len(result.errors)}, warnings={len(result.warnings)}")

    except httpx.ConnectError as e:
        logger.error(f"Connection error: {e}")
        result.is_valid = False
        result.errors.append("Could not connect to Anthropic API. Check your internet connection.")
    except httpx.TimeoutException:
        logger.error("AI validation timed out")
        result.is_valid = False
        result.errors.append("AI validation timed out after 60 seconds. Try again.")
    except Exception as e:
        logger.error(f"AI validation error: {e}", exc_info=True)
        result.is_valid = False
        result.errors.append(f"AI validation failed: {str(e)}")

    return result


def _validate_with_monticore(sysml_text: str) -> ValidationResult:
    """Validate using MontiCore SysML v2 JAR (fallback)."""
    result = ValidationResult(source="compiler")

    java_bin = _find_java()
    if not java_bin:
        result.source = "compiler_unavailable"
        return result

    jar_path = COMPILER_JAR
    if not os.path.exists(jar_path):
        result.source = "compiler_unavailable"
        return result

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="modelmerge_")
        temp_file = os.path.join(temp_dir, "merged_model.sysml")
        with open(temp_file, 'w') as f:
            f.write(sysml_text)

        cmd = [java_bin, "-Xmx1g", "-jar", jar_path, "-i", temp_file]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, cwd=temp_dir,
        )

        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")

        if proc.returncode == 0:
            result.is_valid = True
            result.warnings.append("MontiCore SysML v2 parser: validation passed")
        else:
            result.is_valid = False
            for line in combined.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "error" in line.lower() or line.startswith("0x"):
                    result.errors.append(line)
                elif "warning" in line.lower():
                    result.warnings.append(line)

    except subprocess.TimeoutExpired:
        result.is_valid = False
        result.errors.append("Compiler timed out after 60 seconds")
    except Exception as e:
        result.is_valid = False
        result.errors.append(f"Compiler invocation failed: {str(e)}")
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return result


def _find_java() -> str | None:
    """Find Java executable."""
    for path in [
        os.environ.get("JAVA_PATH", "java"),
        "/usr/bin/java",
        "/usr/local/bin/java",
        "/opt/homebrew/bin/java",
    ]:
        if path and shutil.which(path):
            return path
    java_home = os.environ.get("JAVA_HOME", "")
    if java_home:
        java_bin = os.path.join(java_home, "bin", "java")
        if os.path.exists(java_bin):
            return java_bin
    return None
