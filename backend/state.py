from typing import Literal, Optional, TypedDict


class MarketSignal(TypedDict):
    source: str
    content: str
    retrieved_at: str
    confidence: float


class PolicyHit(TypedDict):
    chunk_text: str
    score: float
    source_doc: str
    risk_category: str


class NodeError(TypedDict):
    node: str
    reason: str
    fallback_used: bool


class State(TypedDict):
    request_id: str
    vendor_name: str
    spend_amount: Optional[float]
    category: str
    market_data: list[MarketSignal]
    policy_hits: list[PolicyHit]
    contract_flags: list[str]
    risk_brief: str
    risk_score: int
    confidence: float
    recommendation: Literal["Approve", "Escalate", "Reject", "Pending"]
    errors: list[NodeError]
    partial_output: bool


_BLOCKING_KEYWORDS = frozenset([
    "dpa", "data protection act", "violation",
    "sanction", "sanctions", "ofac",
    "debarment", "debarred", "excluded",
])


def infer_severity(content: str) -> Literal["blocking", "advisory"]:
    lower = content.lower()
    if any(kw in lower for kw in _BLOCKING_KEYWORDS):
        return "blocking"
    return "advisory"


def compute_confidence(state: State) -> float:
    score = 1.0
    if not state["market_data"]:
        score -= 0.35
    elif not any(s["source"] == "erp" for s in state["market_data"]):
        score -= 0.15
    if not state["policy_hits"]:
        score -= 0.35
    if not state["contract_flags"]:
        score -= 0.10
    return round(max(score, 0.1), 2)


def should_synthesize(state: State) -> str:
    scout_hard_fail = any(
        e["node"] == "market_scout" and not e["fallback_used"] for e in state["errors"]
    )
    librarian_hard_fail = any(
        e["node"] == "policy_librarian" and not e["fallback_used"] for e in state["errors"]
    )
    if scout_hard_fail and librarian_hard_fail:
        return "human_review"
    return "risk_synthesizer"
