"""Observability tests — OpenTelemetry/OTLP (Dynatrace) backend.

Uses in-memory OTel readers/exporters so metrics and spans can be asserted
without a live Dynatrace tenant.
"""

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from observability import (
    OtelTracker,
    RequestLatencyMiddleware,
    compute_cost,
    node_span,
)

# ---------------------------------------------------------------------------
# Helpers — in-memory OTel plumbing
# ---------------------------------------------------------------------------


def _tracker() -> tuple[OtelTracker, InMemoryMetricReader, InMemorySpanExporter]:
    reader = InMemoryMetricReader()
    meter = MeterProvider(metric_readers=[reader]).get_meter("test")

    span_exporter = InMemorySpanExporter()
    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(span_exporter))
    tracer = tp.get_tracer("test")

    return OtelTracker(meter=meter, tracer=tracer), reader, span_exporter


def _points(reader: InMemoryMetricReader, metric_name: str) -> list:
    """Return all data points recorded under a given metric name."""
    data = reader.get_metrics_data()
    out = []
    if data is None:
        return out
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                if metric.name == metric_name:
                    out.extend(metric.data.data_points)
    return out


def _one(reader: InMemoryMetricReader, metric_name: str):
    pts = _points(reader, metric_name)
    assert len(pts) == 1, f"expected 1 point for {metric_name}, got {len(pts)}"
    return pts[0]


# ---------------------------------------------------------------------------
# Cycle 1 — node duration histogram with correct attributes
# ---------------------------------------------------------------------------


def test_track_node_duration_records_histogram_with_node_and_request_id():
    tracker, reader, _ = _tracker()
    tracker.track_node_duration("req-1", "market_scout", 123.4, False)

    pt = _one(reader, "node_duration_ms")
    assert pt.sum == pytest.approx(123.4)
    assert pt.attributes["request_id"] == "req-1"
    assert pt.attributes["node_name"] == "market_scout"


def test_track_node_duration_partial_output_true_attribute():
    tracker, reader, _ = _tracker()
    tracker.track_node_duration("req-2", "risk_synthesizer", 200.0, True)
    assert _one(reader, "node_duration_ms").attributes["partial_output"] is True


def test_track_node_duration_partial_output_false_attribute():
    tracker, reader, _ = _tracker()
    tracker.track_node_duration("req-3", "policy_librarian", 50.0, False)
    assert _one(reader, "node_duration_ms").attributes["partial_output"] is False


# ---------------------------------------------------------------------------
# Cycle 2 — recommendation counter
# ---------------------------------------------------------------------------


def test_track_recommendation_increments_counter_with_dimension():
    tracker, reader, _ = _tracker()
    tracker.track_recommendation("req-4", "Approve", False)

    pt = _one(reader, "assessment_total")
    assert pt.value == 1
    assert pt.attributes["request_id"] == "req-4"
    assert pt.attributes["recommendation"] == "Approve"


def test_track_recommendation_partial_output_attribute():
    tracker, reader, _ = _tracker()
    tracker.track_recommendation("req-5", "Escalate", True)
    assert _one(reader, "assessment_total").attributes["partial_output"] is True


# ---------------------------------------------------------------------------
# Cycle 3 — LLM tokens: histograms + GenAI span
# ---------------------------------------------------------------------------


def test_track_llm_tokens_records_prompt_and_completion_histograms():
    tracker, reader, _ = _tracker()
    tracker.track_llm_tokens("req-6", "risk_synthesizer", prompt_tokens=800, completion_tokens=200)

    assert _one(reader, "llm_prompt_tokens").sum == 800
    assert _one(reader, "llm_completion_tokens").sum == 200


def test_track_llm_tokens_request_id_on_metrics():
    tracker, reader, _ = _tracker()
    tracker.track_llm_tokens("req-7", "risk_synthesizer", prompt_tokens=100, completion_tokens=50)
    assert _one(reader, "llm_prompt_tokens").attributes["request_id"] == "req-7"
    assert _one(reader, "llm_completion_tokens").attributes["request_id"] == "req-7"


def test_track_llm_tokens_emits_genai_span_with_semantic_attributes():
    tracker, _, spans = _tracker()
    tracker.track_llm_tokens("req-6", "risk_synthesizer", prompt_tokens=800, completion_tokens=200)

    finished = spans.get_finished_spans()
    assert len(finished) == 1
    attrs = finished[0].attributes
    assert attrs["gen_ai.usage.input_tokens"] == 800
    assert attrs["gen_ai.usage.output_tokens"] == 200
    assert attrs["gen_ai.request.model"]  # model name present
    assert attrs["request_id"] == "req-6"


# ---------------------------------------------------------------------------
# Cycle 4 — compute_cost (pure)
# ---------------------------------------------------------------------------


def test_compute_cost_zero_tokens_returns_zero():
    assert compute_cost(0, 0) == 0.0


def test_compute_cost_1k_prompt_tokens():
    assert compute_cost(1000, 0) == pytest.approx(0.005)


def test_compute_cost_1k_completion_tokens():
    assert compute_cost(0, 1000) == pytest.approx(0.015)


def test_compute_cost_mixed_tokens():
    assert compute_cost(800, 200) == pytest.approx(0.007)


# ---------------------------------------------------------------------------
# Cycle 5 — cost-per-assessment metric
# ---------------------------------------------------------------------------


def test_track_cost_per_assessment_records_computed_cost():
    tracker, reader, _ = _tracker()
    tracker.track_cost_per_assessment("req-8", prompt_tokens=1000, completion_tokens=1000)

    pt = _one(reader, "cost_per_assessment_usd")
    assert pt.sum == pytest.approx(0.005 + 0.015)  # 0.020
    assert pt.attributes["request_id"] == "req-8"


# ---------------------------------------------------------------------------
# Cycle 6 — Tavily and Search latency metrics
# ---------------------------------------------------------------------------


def test_track_tavily_latency_records_metric_with_request_id():
    tracker, reader, _ = _tracker()
    tracker.track_tavily_latency("req-9", 450.5)
    pt = _one(reader, "tavily_latency_ms")
    assert pt.sum == pytest.approx(450.5)
    assert pt.attributes["request_id"] == "req-9"


def test_track_search_latency_records_metric_with_request_id():
    tracker, reader, _ = _tracker()
    tracker.track_search_latency("req-10", 88.2)
    pt = _one(reader, "search_latency_ms")
    assert pt.sum == pytest.approx(88.2)
    assert pt.attributes["request_id"] == "req-10"


# ---------------------------------------------------------------------------
# Cycle 7 — RequestLatencyMiddleware
# ---------------------------------------------------------------------------


async def test_middleware_records_request_latency_with_request_id():
    tracker, reader, _ = _tracker()

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

    pt = _one(reader, "request_latency_ms")
    assert pt.attributes["request_id"] == "req-11"


async def test_middleware_skips_non_http_scopes():
    tracker, reader, _ = _tracker()

    async def app(scope, receive, send):
        pass

    middleware = RequestLatencyMiddleware(app, tracker)
    await middleware({"type": "lifespan"}, None, None)

    assert _points(reader, "request_latency_ms") == []


# ---------------------------------------------------------------------------
# Cycle 8 — node_span context manager
# ---------------------------------------------------------------------------


async def test_node_span_records_duration_on_exit():
    tracker, reader, spans = _tracker()

    async with node_span(tracker, "req-12", "market_scout", False):
        pass

    pt = _one(reader, "node_duration_ms")
    assert pt.attributes["request_id"] == "req-12"
    assert pt.attributes["node_name"] == "market_scout"
    # node span itself is also exported
    assert any(s.name == "node market_scout" for s in spans.get_finished_spans())


async def test_node_span_still_records_duration_when_node_raises():
    tracker, reader, _ = _tracker()

    with pytest.raises(ValueError):
        async with node_span(tracker, "req-13", "policy_librarian", True):
            raise ValueError("node exploded")

    pt = _one(reader, "node_duration_ms")
    assert pt.attributes["partial_output"] is True
