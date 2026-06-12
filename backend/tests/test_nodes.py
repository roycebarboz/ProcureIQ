import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agents.market_scout import market_scout_node
from agents.policy_librarian import policy_librarian_node
from state import MarketSignal, NodeError, PolicyHit, State, should_synthesize
from tools.erp_mock import get_erp_spend


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
# Slice 1 — ERP miss
# ---------------------------------------------------------------------------


def test_erp_unknown_vendor_returns_empty_signal_with_zero_confidence():
    signal = get_erp_spend("VendorThatDoesNotExist")
    assert signal["source"] == "erp"
    assert signal["content"] == ""
    assert signal["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Slice 2 — Tavily timeout
# ---------------------------------------------------------------------------


async def test_scout_tavily_timeout_writes_node_error_and_empty_market_data():
    async def _timeout(*_args, **_kwargs):
        raise asyncio.TimeoutError

    state = _base_state(vendor_name="VendorThatDoesNotExist")
    with patch("agents.market_scout.tavily_search", side_effect=_timeout):
        result = await market_scout_node(state)

    assert result["market_data"] == []
    assert result["partial_output"] is True
    errors: list[NodeError] = result["errors"]
    assert len(errors) == 1
    assert errors[0]["node"] == "market_scout"
    assert errors[0]["reason"] == "timeout_tavily"
    assert errors[0]["fallback_used"] is True


# ---------------------------------------------------------------------------
# Slice 3 — Tavily success
# ---------------------------------------------------------------------------


async def test_scout_tavily_success_writes_web_search_signal():
    async def _mock_search(*_args, **_kwargs):
        return [{"content": "Acme Corp rated AA supplier", "score": 0.87}]

    state = _base_state(vendor_name="Acme Corp")
    with patch("agents.market_scout.tavily_search", side_effect=_mock_search):
        result = await market_scout_node(state)

    web_signals = [s for s in result["market_data"] if s["source"] == "web_search"]
    assert len(web_signals) == 1
    assert web_signals[0]["confidence"] > 0
    assert result["errors"] == []
    assert result["partial_output"] is False


# ---------------------------------------------------------------------------
# Slice 4 — ERP miss + partial failure routing
# ---------------------------------------------------------------------------


async def test_scout_erp_miss_does_not_fail_node():
    async def _mock_search(*_args, **_kwargs):
        return [{"content": "Some news", "score": 0.7}]

    state = _base_state(vendor_name="VendorThatDoesNotExist")
    with patch("agents.market_scout.tavily_search", side_effect=_mock_search):
        result = await market_scout_node(state)

    erp_signals = [s for s in result["market_data"] if s["source"] == "erp"]
    assert len(erp_signals) == 1
    assert erp_signals[0]["confidence"] == 0.0
    assert erp_signals[0]["content"] == ""
    assert result["errors"] == []


def test_scout_timeout_fallback_routes_to_risk_synthesizer():
    error: NodeError = {"node": "market_scout", "reason": "timeout_tavily", "fallback_used": True}
    state = _base_state(errors=[error], market_data=[])
    assert should_synthesize(state) == "risk_synthesizer"


# ---------------------------------------------------------------------------
# Slice 5 — Policy Librarian
# ---------------------------------------------------------------------------


async def test_librarian_zero_chunks_writes_node_error_and_partial_output():
    async def _no_results(*_args, **_kwargs):
        return []

    state = _base_state(category="IT Services")
    with patch("agents.policy_librarian.search_policy_chunks", side_effect=_no_results):
        result = await policy_librarian_node(state)

    assert result["policy_hits"] == []
    assert result["partial_output"] is True
    errors: list[NodeError] = result["errors"]
    assert len(errors) == 1
    assert errors[0]["node"] == "policy_librarian"
    assert errors[0]["reason"] == "no_relevant_chunks_retrieved"
    assert errors[0]["fallback_used"] is True


async def test_librarian_success_writes_policy_hits_with_correct_shape():
    async def _mock_search(*_args, **_kwargs):
        return [
            {
                "chunk_text": "Vendors with DPA obligations must encrypt data at rest.",
                "score": 0.91,
                "source_doc": "ProcureIQ Supplier Risk Policy v2.pdf",
            }
        ]

    state = _base_state(category="IT Services")
    with patch("agents.policy_librarian.search_policy_chunks", side_effect=_mock_search):
        result = await policy_librarian_node(state)

    assert len(result["policy_hits"]) == 1
    hit: PolicyHit = result["policy_hits"][0]
    assert hit["chunk_text"] == "Vendors with DPA obligations must encrypt data at rest."
    assert hit["score"] == 0.91
    assert hit["source_doc"] == "ProcureIQ Supplier Risk Policy v2.pdf"
    assert hit["risk_category"] == "blocking"  # "dpa" keyword triggers blocking
    assert result["errors"] == []
    assert result["partial_output"] is False


def test_librarian_zero_chunk_fallback_routes_to_risk_synthesizer():
    error: NodeError = {
        "node": "policy_librarian",
        "reason": "no_relevant_chunks_retrieved",
        "fallback_used": True,
    }
    state = _base_state(errors=[error], policy_hits=[])
    assert should_synthesize(state) == "risk_synthesizer"
