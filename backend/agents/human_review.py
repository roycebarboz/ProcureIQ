from state import State


async def human_review_node(state: State) -> dict:
    failed_nodes = [e["node"] for e in state["errors"] if not e["fallback_used"]]
    brief = (
        "[PENDING HUMAN REVIEW] Automated assessment could not complete. "
        f"Critical failures in: {', '.join(failed_nodes) if failed_nodes else 'unknown nodes'}. "
        "Manual review required before any procurement decision is made."
    )
    return {
        "recommendation": "Pending",
        "risk_score": 0,
        "confidence": 0.0,
        "risk_brief": brief,
        "partial_output": True,
    }
