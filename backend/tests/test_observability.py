from unittest.mock import MagicMock, call

import pytest

from observability import AppInsightsTracker, RequestLatencyMiddleware, compute_cost, node_span


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tracker() -> tuple[AppInsightsTracker, MagicMock]:
    client = MagicMock()
    return AppInsightsTracker(client=client), client


# ---------------------------------------------------------------------------
# Cycle 1 — track_node_duration emits metric with correct properties
# ---------------------------------------------------------------------------


def test_track_node_duration_sends_metric_with_node_name_and_request_id():
    tracker, client = _tracker()
    tracker.track_node_duration("req-1", "market_scout", 123.4, False)

    client.track_metric.assert_called_once()
    name, value = client.track_metric.call_args.args
    props = client.track_metric.call_args.kwargs.get("properties", {})

    assert name == "node_duration_ms"
    assert value == pytest.approx(123.4)
    assert props["request_id"] == "req-1"
    assert props["node_name"] == "market_scout"


# ---------------------------------------------------------------------------
# Cycle 2 — partial_output propagates as string property
# ---------------------------------------------------------------------------


def test_track_node_duration_partial_output_true_in_properties():
    tracker, client = _tracker()
    tracker.track_node_duration("req-2", "risk_synthesizer", 200.0, True)

    props = client.track_metric.call_args.kwargs.get("properties", {})
    assert props["partial_output"] == "True"


def test_track_node_duration_partial_output_false_in_properties():
    tracker, client = _tracker()
    tracker.track_node_duration("req-3", "policy_librarian", 50.0, False)

    props = client.track_metric.call_args.kwargs.get("properties", {})
    assert props["partial_output"] == "False"


# ---------------------------------------------------------------------------
# Cycle 3 — track_recommendation emits custom event
# ---------------------------------------------------------------------------


def test_track_recommendation_sends_event_with_recommendation_dimension():
    tracker, client = _tracker()
    tracker.track_recommendation("req-4", "Approve", False)

    client.track_event.assert_called_once()
    name = client.track_event.call_args.args[0]
    props = client.track_event.call_args.kwargs.get("properties", {})

    assert name == "assessment_complete"
    assert props["request_id"] == "req-4"
    assert props["recommendation"] == "Approve"


def test_track_recommendation_partial_output_in_event_properties():
    tracker, client = _tracker()
    tracker.track_recommendation("req-5", "Escalate", True)

    props = client.track_event.call_args.kwargs.get("properties", {})
    assert props["partial_output"] == "True"


# ---------------------------------------------------------------------------
# Cycle 4 — track_llm_tokens emits prompt and completion metrics
# ---------------------------------------------------------------------------


def test_track_llm_tokens_sends_two_metrics():
    tracker, client = _tracker()
    tracker.track_llm_tokens("req-6", "risk_synthesizer", prompt_tokens=800, completion_tokens=200)

    assert client.track_metric.call_count == 2
    calls = client.track_metric.call_args_list
    names = [c.args[0] for c in calls]
    assert "llm_prompt_tokens" in names
    assert "llm_completion_tokens" in names


def test_track_llm_tokens_correct_values():
    tracker, client = _tracker()
    tracker.track_llm_tokens("req-6", "risk_synthesizer", prompt_tokens=800, completion_tokens=200)

    calls = {c.args[0]: c for c in client.track_metric.call_args_list}
    assert calls["llm_prompt_tokens"].args[1] == 800
    assert calls["llm_completion_tokens"].args[1] == 200


def test_track_llm_tokens_request_id_in_properties():
    tracker, client = _tracker()
    tracker.track_llm_tokens("req-7", "risk_synthesizer", prompt_tokens=100, completion_tokens=50)

    for c in client.track_metric.call_args_list:
        assert c.kwargs.get("properties", {})["request_id"] == "req-7"


# ---------------------------------------------------------------------------
# Cycle 5 — compute_cost returns correct USD cost
# ---------------------------------------------------------------------------


def test_compute_cost_zero_tokens_returns_zero():
    assert compute_cost(0, 0) == 0.0


def test_compute_cost_1k_prompt_tokens():
    # $0.005 per 1K prompt tokens
    assert compute_cost(1000, 0) == pytest.approx(0.005)


def test_compute_cost_1k_completion_tokens():
    # $0.015 per 1K completion tokens
    assert compute_cost(0, 1000) == pytest.approx(0.015)


def test_compute_cost_mixed_tokens():
    # 800 prompt + 200 completion: 0.8*0.005 + 0.2*0.015 = 0.004 + 0.003 = 0.007
    assert compute_cost(800, 200) == pytest.approx(0.007)


# ---------------------------------------------------------------------------
# Cycle 6 — track_cost_per_assessment sends cost metric
# ---------------------------------------------------------------------------


def test_track_cost_per_assessment_sends_metric_with_computed_cost():
    tracker, client = _tracker()
    tracker.track_cost_per_assessment("req-8", prompt_tokens=1000, completion_tokens=1000)

    client.track_metric.assert_called_once()
    name, value = client.track_metric.call_args.args
    props = client.track_metric.call_args.kwargs.get("properties", {})

    assert name == "cost_per_assessment_usd"
    assert value == pytest.approx(0.005 + 0.015)  # 0.020
    assert props["request_id"] == "req-8"


# ---------------------------------------------------------------------------
# Cycle 7 — Tavily and Search latency metrics
# ---------------------------------------------------------------------------


def test_track_tavily_latency_sends_metric_with_request_id():
    tracker, client = _tracker()
    tracker.track_tavily_latency("req-9", 450.5)

    client.track_metric.assert_called_once()
    name, value = client.track_metric.call_args.args
    props = client.track_metric.call_args.kwargs.get("properties", {})

    assert name == "tavily_latency_ms"
    assert value == pytest.approx(450.5)
    assert props["request_id"] == "req-9"


def test_track_search_latency_sends_metric_with_request_id():
    tracker, client = _tracker()
    tracker.track_search_latency("req-10", 88.2)

    client.track_metric.assert_called_once()
    name, value = client.track_metric.call_args.args
    props = client.track_metric.call_args.kwargs.get("properties", {})

    assert name == "search_latency_ms"
    assert value == pytest.approx(88.2)
    assert props["request_id"] == "req-10"


# ---------------------------------------------------------------------------
# Cycle 8 — RequestLatencyMiddleware logs latency + request_id
# ---------------------------------------------------------------------------


async def test_middleware_logs_request_latency_with_request_id():
    tracker, client = _tracker()

    # Minimal ASGI app that just completes
    async def app(scope, receive, send):
        pass

    middleware = RequestLatencyMiddleware(app, tracker)
    scope = {
        "type": "http",
        "headers": [(b"x-request-id", b"req-11")],
        "path": "/assess",
        "method": "POST",
    }

    await middleware(scope, None, None)

    client.track_metric.assert_called_once()
    name = client.track_metric.call_args.args[0]
    props = client.track_metric.call_args.kwargs.get("properties", {})

    assert name == "request_latency_ms"
    assert props["request_id"] == "req-11"


async def test_middleware_skips_non_http_scopes():
    tracker, client = _tracker()

    async def app(scope, receive, send):
        pass

    middleware = RequestLatencyMiddleware(app, tracker)
    scope = {"type": "lifespan"}
    await middleware(scope, None, None)

    client.track_metric.assert_not_called()


# ---------------------------------------------------------------------------
# Cycle 9 — node_span context manager calls track_node_duration
# ---------------------------------------------------------------------------


async def test_node_span_calls_track_node_duration_on_exit():
    tracker, client = _tracker()

    async with node_span(tracker, "req-12", "market_scout", False):
        pass  # simulate node work

    client.track_metric.assert_called_once()
    name = client.track_metric.call_args.args[0]
    props = client.track_metric.call_args.kwargs.get("properties", {})

    assert name == "node_duration_ms"
    assert props["request_id"] == "req-12"
    assert props["node_name"] == "market_scout"


async def test_node_span_still_tracks_duration_when_node_raises():
    tracker, client = _tracker()

    with pytest.raises(ValueError):
        async with node_span(tracker, "req-13", "policy_librarian", True):
            raise ValueError("node exploded")

    # Duration must still be tracked even on exception
    client.track_metric.assert_called_once()
    props = client.track_metric.call_args.kwargs.get("properties", {})
    assert props["partial_output"] == "True"
