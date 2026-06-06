from state import (
    MarketSignal,
    NodeError,
    PolicyHit,
    State,
    compute_confidence,
    infer_severity,
    should_synthesize,
)


def _base_state(**overrides) -> State:
    base: State = {
        "request_id": "test-001",
        "vendor_name": "Acme Corp",
        "spend_amount": 50000.0,
        "category": "IT Services",
        "market_data": [],
        "policy_hits": [],
        "contract_flags": [],
        "risk_brief": "",
        "risk_score": 0,
        "confidence": 0.0,
        "recommendation": "Pending",
        "errors": [],
        "partial_output": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# should_synthesize
# ---------------------------------------------------------------------------


def test_should_synthesize_no_failures_routes_to_risk_synthesizer():
    state = _base_state(errors=[])
    assert should_synthesize(state) == "risk_synthesizer"


def test_should_synthesize_both_hard_fail_routes_to_human_review():
    errors: list[NodeError] = [
        {"node": "market_scout", "reason": "timeout", "fallback_used": False},
        {"node": "policy_librarian", "reason": "search unavailable", "fallback_used": False},
    ]
    state = _base_state(errors=errors)
    assert should_synthesize(state) == "human_review"


def test_should_synthesize_scout_hard_fail_only_routes_to_risk_synthesizer():
    errors: list[NodeError] = [
        {"node": "market_scout", "reason": "timeout", "fallback_used": False},
    ]
    state = _base_state(errors=errors)
    assert should_synthesize(state) == "risk_synthesizer"


def test_should_synthesize_librarian_hard_fail_only_routes_to_risk_synthesizer():
    errors: list[NodeError] = [
        {"node": "policy_librarian", "reason": "search unavailable", "fallback_used": False},
    ]
    state = _base_state(errors=errors)
    assert should_synthesize(state) == "risk_synthesizer"


# ---------------------------------------------------------------------------
# compute_confidence
# ---------------------------------------------------------------------------


def _erp_signal() -> MarketSignal:
    return {
        "source": "erp",
        "content": "spend history available",
        "retrieved_at": "2026-06-05T00:00:00Z",
        "confidence": 1.0,
    }


def _policy_hit() -> PolicyHit:
    return {
        "chunk_text": "Vendor must hold ISO 27001.",
        "score": 0.95,
        "source_doc": "procurement-policy.pdf",
        "risk_category": "compliance",
    }


def test_compute_confidence_all_data_returns_1_0():
    state = _base_state(
        market_data=[_erp_signal()],
        policy_hits=[_policy_hit()],
        contract_flags=["MSA signed"],
    )
    assert compute_confidence(state) == 1.0


def test_compute_confidence_no_erp_source_returns_0_85():
    web_signal: MarketSignal = {
        "source": "web_search",
        "content": "Vendor news available",
        "retrieved_at": "2026-06-05T00:00:00Z",
        "confidence": 0.8,
    }
    state = _base_state(
        market_data=[web_signal],
        policy_hits=[_policy_hit()],
        contract_flags=["MSA signed"],
    )
    assert compute_confidence(state) == 0.85


def test_compute_confidence_no_market_data_returns_0_65():
    state = _base_state(
        market_data=[],
        policy_hits=[_policy_hit()],
        contract_flags=["MSA signed"],
    )
    assert compute_confidence(state) == 0.65


def test_compute_confidence_no_policy_hits_returns_0_65():
    state = _base_state(
        market_data=[_erp_signal()],
        policy_hits=[],
        contract_flags=["MSA signed"],
    )
    assert compute_confidence(state) == 0.65


def test_compute_confidence_no_market_and_no_policy_returns_0_30():
    state = _base_state(
        market_data=[],
        policy_hits=[],
        contract_flags=["MSA signed"],
    )
    assert compute_confidence(state) == 0.30


# ---------------------------------------------------------------------------
# infer_severity
# ---------------------------------------------------------------------------


def test_infer_severity_dpa_violation_is_blocking():
    assert infer_severity("Vendor was found in violation of DPA requirements") == "blocking"


def test_infer_severity_sanctions_hit_is_blocking():
    assert infer_severity("Entity appears on OFAC sanctions list") == "blocking"


def test_infer_severity_debarment_is_blocking():
    assert infer_severity("Supplier subject to federal debarment proceedings") == "blocking"


def test_infer_severity_general_advisory_content_is_advisory():
    assert infer_severity("Vendor should consider improving documentation practices") == "advisory"
