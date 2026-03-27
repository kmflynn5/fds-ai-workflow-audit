from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class EnrichmentResult:
    additional_failure_modes: list[dict] = field(default_factory=list)
    eval_criteria: list[dict] = field(default_factory=list)
    guardrail_recommendations: list[dict] = field(default_factory=list)
    model_mismatch_flags: list[dict] = field(default_factory=list)
    implicit_assumptions: list[dict] = field(default_factory=list)
    raw_response: str = ""


ENRICHMENT_PROMPT = """You are an AI systems architect reviewing a production AI workflow for risk and quality.

WORKFLOW:
{workflow_yaml}

RULE-BASED ASSESSMENT:
{engine_output}

Enhance this assessment:
1. Identify failure modes the rule-based engine may have missed
2. Suggest specific eval criteria for each step (what does "correct" look like?)
3. Recommend specific guardrail implementations (not just "add a guardrail")
4. Identify any steps where the model choice seems mismatched to task complexity
5. Flag any implicit assumptions in the workflow that could cause silent failures

Output as JSON with these keys:
- additional_failure_modes: [{step_id, failure_type, description, mitigation}]
- eval_criteria: [{step_id, criteria, measurement_method}]
- guardrail_recommendations: [{step_id, guardrail_type, implementation}]
- model_mismatch_flags: [{step_id, current_model, suggested_model, reason}]
- implicit_assumptions: [{step_id, assumption, risk, recommendation}]
"""


def is_available() -> bool:
    """Check if the Claude API is available (API key set and package installed)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401

        return True
    except ImportError:
        return False


def enrich_assessment(
    workflow_yaml: str,
    engine_output: dict,
    model: str = "claude-sonnet-4-20250514",
) -> EnrichmentResult:
    """Send workflow + rule-based output to Claude for enhanced analysis.

    Raises ImportError if anthropic package is not installed.
    Raises RuntimeError if ANTHROPIC_API_KEY is not set.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")

    try:
        import anthropic
    except ImportError as e:
        raise ImportError(
            "The 'anthropic' package is required for Claude enrichment. Install it with: uv sync --extra claude"
        ) from e

    client = anthropic.Anthropic()

    prompt = ENRICHMENT_PROMPT.format(
        workflow_yaml=workflow_yaml,
        engine_output=json.dumps(engine_output, indent=2),
    )

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text

    # Try to parse the JSON response
    try:
        # Handle case where response might have markdown code fences
        text = raw_text.strip()
        if text.startswith("```"):
            # Remove code fences
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        parsed = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        # If parsing fails, return raw response with empty structured fields
        return EnrichmentResult(raw_response=raw_text)

    return EnrichmentResult(
        additional_failure_modes=parsed.get("additional_failure_modes", []),
        eval_criteria=parsed.get("eval_criteria", []),
        guardrail_recommendations=parsed.get("guardrail_recommendations", []),
        model_mismatch_flags=parsed.get("model_mismatch_flags", []),
        implicit_assumptions=parsed.get("implicit_assumptions", []),
        raw_response=raw_text,
    )
