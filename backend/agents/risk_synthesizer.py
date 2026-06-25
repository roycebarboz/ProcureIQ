import json
import os

from openai import AsyncAzureOpenAI

from observability import get_tracker, node_span
from state import State, compute_confidence

_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

_GENERAL_RUBRIC = (
    "[POLICY DATA UNAVAILABLE — apply general procurement rubric: "
    "assess based on vendor category risk, spend exposure, and standard due-diligence norms]"
)


def _build_prompt(state: State) -> str:
    vendor = state["vendor_name"]
    category = state["category"]
    partial = state["partial_output"]

    if state["market_data"]:
        market_section = "\n".join(
            f"- [{s['source']}] {s['content']} (confidence: {s['confidence']})"
            for s in state["market_data"]
        )
    else:
        market_section = (
            "[MARKET DATA UNAVAILABLE — do not infer spend patterns or financial stability]"  # noqa: E501
        )

    if state["policy_hits"]:
        policy_section = "\n".join(
            f"- [{h['risk_category'].upper()}] {h['chunk_text']} "
            f"(source: {h['source_doc']}, score: {h['score']:.2f})"
            for h in state["policy_hits"]
        )
    else:
        policy_section = _GENERAL_RUBRIC

    flags_section = (
        "\n".join(f"- {f}" for f in state["contract_flags"])
        if state["contract_flags"]
        else "None identified."
    )

    degradation_notice = ""
    if partial:
        missing = []
        if not state["market_data"]:
            missing.append("market intelligence")
        if not state["policy_hits"]:
            missing.append("policy retrieval")
        degradation_notice = (
            f"\n\n⚠ DEGRADED ASSESSMENT: {', '.join(missing)} unavailable. "
            "Explicitly acknowledge missing data in your risk_brief. "
            "risk_score MUST be ≤ 6."
        )

    return f"""You are a procurement risk analyst. Assess the following vendor \
and produce a structured JSON risk brief.

Vendor: {vendor}
Category: {category}

## Market Intelligence
{market_section}

## Policy Hits
{policy_section}

## Contract Flags
{flags_section}
{degradation_notice}

Respond ONLY with valid JSON matching this exact schema:
{{
  "risk_score": <integer 1-10>,
  "recommendation": <"Approve" | "Escalate" | "Reject">,
  "risk_brief": <string, 2-4 sentences summarising risk posture>
}}

Rules:
- risk_score 1-3 → Approve, 4-6 → Escalate, 7-10 → Reject (use judgment for borderline cases)
- Any BLOCKING policy hit → recommendation must be Escalate or Reject
- Degraded assessment → risk_score ≤ 6, risk_brief must acknowledge missing data"""


async def _call_llm(prompt: str) -> tuple[dict, int, int]:
    """Returns (parsed_output, prompt_tokens, completion_tokens)."""
    client = AsyncAzureOpenAI(
        azure_endpoint=_ENDPOINT,
        api_key=_KEY,
        api_version=_API_VERSION,
    )
    response = await client.chat.completions.create(
        model=_DEPLOYMENT,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    return json.loads(response.choices[0].message.content), prompt_tokens, completion_tokens


async def risk_synthesizer_node(state: State) -> dict:
    tracker = get_tracker()
    request_id = state["request_id"]

    async with node_span(tracker, request_id, "risk_synthesizer", state["partial_output"]):
        prompt = _build_prompt(state)
        llm_output, prompt_tokens, completion_tokens = await _call_llm(prompt)

        tracker.track_llm_tokens(request_id, "risk_synthesizer", prompt_tokens, completion_tokens)
        tracker.track_cost_per_assessment(request_id, prompt_tokens, completion_tokens)

        risk_score = int(llm_output.get("risk_score", 5))
        recommendation = llm_output.get("recommendation", "Escalate")
        risk_brief = llm_output.get("risk_brief", "")

        if state["partial_output"] and risk_score > 6:
            risk_score = 6

        confidence = compute_confidence(state)
        tracker.track_recommendation(request_id, recommendation, state["partial_output"])

        return {
            "risk_score": risk_score,
            "recommendation": recommendation,
            "risk_brief": risk_brief,
            "confidence": confidence,
            "partial_output": state["partial_output"],
        }
