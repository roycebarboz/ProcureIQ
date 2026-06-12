import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.graph import END, START, StateGraph

from api import app
from state import State, should_synthesize


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health_returns_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_post_assess_returns_event_stream(client):
    async with client.stream(
        "POST", "/assess", json={"vendor_name": "Acme", "category": "IT Services"}
    ) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]


async def _collect_events(client, payload: dict) -> list[dict]:
    events, current = [], {}
    async with client.stream("POST", "/assess", json=payload) as r:
        async for line in r.aiter_lines():
            if line.startswith("event:"):
                current["event"] = line[6:].strip()
            elif line.startswith("data:"):
                current["data"] = json.loads(line[5:].strip())
            elif line == "" and current:
                events.append(current)
                current = {}
    return events


async def test_sse_events_arrive_in_correct_order(client):
    events = await _collect_events(
        client, {"vendor_name": "Acme", "category": "IT Services"}
    )
    assert [e["event"] for e in events] == [
        "scout_complete",
        "librarian_complete",
        "assessment_complete",
    ]


async def test_request_id_present_in_every_event(client):
    events = await _collect_events(
        client, {"vendor_name": "Acme", "category": "IT Services"}
    )
    assert all("request_id" in e["data"] for e in events)
    request_ids = {e["data"]["request_id"] for e in events}
    assert len(request_ids) == 1


async def test_get_result_returns_final_state_after_stream(client):
    events = await _collect_events(
        client, {"vendor_name": "Acme", "category": "IT Services"}
    )
    request_id = events[0]["data"]["request_id"]
    r = await client.get(f"/assess/{request_id}/result")
    assert r.status_code == 200
    result = r.json()
    assert result["request_id"] == request_id
    assert result["recommendation"] in ("Approve", "Escalate", "Reject", "Pending")
    assert result["risk_score"] >= 0


async def test_get_result_returns_404_for_unknown_request_id(client):
    r = await client.get("/assess/nonexistent-id/result")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Slice 6 — Risk Synthesizer integration
# ---------------------------------------------------------------------------


def _initial_state(**overrides) -> State:
    base: State = {
        "request_id": "integ-001",
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


async def test_happy_path_full_pipeline_produces_valid_brief():
    from graph import build_graph

    mock_llm_result = {
        "risk_score": 3,
        "recommendation": "Approve",
        "risk_brief": "Acme Corp demonstrates strong financial performance and compliance posture with no blocking flags.",
    }

    with (
        patch(
            "agents.market_scout.tavily_search",
            new=AsyncMock(return_value=[{"content": "Acme Corp rated AA supplier", "score": 0.9}]),
        ),
        patch(
            "agents.policy_librarian.search_policy_chunks",
            new=AsyncMock(return_value=[{
                "chunk_text": "Vendors must comply with FAR Part 9 qualification requirements.",
                "score": 0.88,
                "source_doc": "far_part_9.txt",
            }]),
        ),
        patch(
            "agents.risk_synthesizer._call_llm",
            new=AsyncMock(return_value=(mock_llm_result, 0, 0)),
        ),
    ):
        g = build_graph()
        result = await g.ainvoke(_initial_state(contract_flags=["NET30"]))

    assert result["risk_brief"] != ""
    assert 1 <= result["risk_score"] <= 10
    assert result["confidence"] == 1.0
    assert result["recommendation"] in ("Approve", "Escalate", "Reject")
    assert result["partial_output"] is False


async def test_both_nodes_hard_fail_routes_to_human_review():
    from agents.human_review import human_review_node

    async def scout_hard_fail(state: State) -> dict:
        return {
            "market_data": [],
            "errors": list(state["errors"]) + [
                {"node": "market_scout", "reason": "critical_unhandled", "fallback_used": False}
            ],
            "partial_output": True,
        }

    async def librarian_hard_fail(state: State) -> dict:
        return {
            "policy_hits": [],
            "errors": list(state["errors"]) + [
                {"node": "policy_librarian", "reason": "critical_unhandled", "fallback_used": False}
            ],
            "partial_output": True,
        }

    async def _no_op(state: State) -> dict:
        return {}

    builder = StateGraph(State)
    builder.add_node("market_scout", scout_hard_fail)
    builder.add_node("policy_librarian", librarian_hard_fail)
    builder.add_node("risk_synthesizer", _no_op)
    builder.add_node("human_review", human_review_node)
    builder.add_edge(START, "market_scout")
    builder.add_edge("market_scout", "policy_librarian")
    builder.add_conditional_edges(
        "policy_librarian",
        should_synthesize,
        {"risk_synthesizer": "risk_synthesizer", "human_review": "human_review"},
    )
    builder.add_edge("risk_synthesizer", END)
    builder.add_edge("human_review", END)
    g = builder.compile()

    result = await g.ainvoke(_initial_state())

    assert result["recommendation"] == "Pending"
    assert result["risk_score"] == 0
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Slice 10 — /dashboard endpoint
# ---------------------------------------------------------------------------


async def test_dashboard_returns_200_with_correct_shape(client):
    r = await client.get("/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "node_latency" in data
    assert "partial_rate" in data
    assert "recommendation_dist" in data
    assert "recent_assessments" in data


async def test_dashboard_recommendation_dist_has_all_four_keys(client):
    r = await client.get("/dashboard")
    dist = r.json()["recommendation_dist"]
    assert set(dist.keys()) == {"Approve", "Escalate", "Reject", "Pending"}


async def test_dashboard_partial_rate_is_zero_when_no_assessments_run(client):
    r = await client.get("/dashboard")
    assert r.json()["partial_rate"] == 0.0


def _mock_pipeline():
    """Context manager that patches all three external calls for dashboard tests."""
    from unittest.mock import AsyncMock, patch
    from contextlib import AsyncExitStack

    mock_llm = {"risk_score": 3, "recommendation": "Approve", "risk_brief": "Low risk."}
    return (
        patch("agents.market_scout.tavily_search",
              new=AsyncMock(return_value=[{"content": "ok", "score": 0.9}])),
        patch("agents.policy_librarian.search_policy_chunks",
              new=AsyncMock(return_value=[{"chunk_text": "ok", "score": 0.8, "source_doc": "doc"}])),
        patch("agents.risk_synthesizer._call_llm",
              new=AsyncMock(return_value=(mock_llm, 0, 0))),
    )


async def test_dashboard_recent_assessments_populated_after_assessment(client):
    patches = _mock_pipeline()
    with patches[0], patches[1], patches[2]:
        await _collect_events(client, {"vendor_name": "DashVendor", "category": "IT Services"})
    r = await client.get("/dashboard")
    recents = r.json()["recent_assessments"]
    vendor_names = [a["vendor_name"] for a in recents]
    assert "DashVendor" in vendor_names


async def test_dashboard_recent_assessment_has_required_fields(client):
    patches = _mock_pipeline()
    with patches[0], patches[1], patches[2]:
        await _collect_events(client, {"vendor_name": "FieldVendor", "category": "IT Services"})
    r = await client.get("/dashboard")
    recents = r.json()["recent_assessments"]
    match = next((a for a in recents if a["vendor_name"] == "FieldVendor"), None)
    assert match is not None
    assert "request_id" in match
    assert "recommendation" in match
    assert "confidence" in match
    assert "timestamp" in match
    assert match["recommendation"] in ("Approve", "Escalate", "Reject", "Pending")


async def test_dashboard_node_latency_populated_after_assessment(client):
    patches = _mock_pipeline()
    with patches[0], patches[1], patches[2]:
        await _collect_events(client, {"vendor_name": "LatencyVendor", "category": "IT Services"})
    r = await client.get("/dashboard")
    latency = r.json()["node_latency"]
    assert isinstance(latency, dict)
    assert len(latency) > 0
    for duration in latency.values():
        assert duration >= 0
