"""Observability — Dynatrace via OpenTelemetry (OTLP).

Replaces Azure Application Insights. Two ingest paths in production:
  - OneAgent  → infra telemetry (configured in Terraform, not here)
  - OTLP      → app traces + metrics, including AI/LLM spans (this module)

AI observability uses the OpenTelemetry GenAI semantic conventions: every LLM
call becomes a span carrying gen_ai.* attributes (model, input/output tokens)
plus derived cost. `request_id` is attached to every span and metric point for
end-to-end correlation.

The public Tracker interface is intentionally unchanged from the prior
App Insights implementation so agent/API call sites need no edits.
"""

import os
import time
from contextlib import asynccontextmanager

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import Counter, Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Azure OpenAI GPT-4o pricing per 1K tokens
_PROMPT_COST_PER_1K = 0.005
_COMPLETION_COST_PER_1K = 0.015

# GenAI span attributes (OTel semantic conventions)
_GEN_AI_SYSTEM = "az.ai.openai"


def compute_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        (prompt_tokens / 1000) * _PROMPT_COST_PER_1K
        + (completion_tokens / 1000) * _COMPLETION_COST_PER_1K,
        6,
    )


def _model_name() -> str:
    return os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT4O", "gpt-4o")


class OtelTracker:
    """Emits OpenTelemetry metrics + spans. Backend-agnostic — exports to
    Dynatrace when `init_telemetry()` has configured an OTLP exporter, and is a
    safe no-op otherwise (the global OTel API returns proxy instruments)."""

    def __init__(self, meter: metrics.Meter | None = None, tracer: trace.Tracer | None = None):
        self._meter = meter or metrics.get_meter("procureiq.observability")
        self._tracer = tracer or trace.get_tracer("procureiq.observability")

        # Histograms (durations / token counts / cost)
        self._h_node = self._meter.create_histogram("node_duration_ms", unit="ms")
        self._h_request = self._meter.create_histogram("request_latency_ms", unit="ms")
        self._h_tavily = self._meter.create_histogram("tavily_latency_ms", unit="ms")
        self._h_search = self._meter.create_histogram("search_latency_ms", unit="ms")
        self._h_prompt = self._meter.create_histogram("llm_prompt_tokens", unit="1")
        self._h_completion = self._meter.create_histogram("llm_completion_tokens", unit="1")
        self._h_cost = self._meter.create_histogram("cost_per_assessment_usd", unit="USD")

        # Counters
        self._c_assessment = self._meter.create_counter("assessment_total", unit="1")

    # ── node + request timing ──────────────────────────────────────────────
    def track_node_duration(
        self, request_id: str, node_name: str, duration_ms: float, partial_output: bool
    ) -> None:
        self._h_node.record(
            duration_ms,
            {"request_id": request_id, "node_name": node_name, "partial_output": partial_output},
        )

    def track_request_latency(self, request_id: str, duration_ms: float) -> None:
        self._h_request.record(duration_ms, {"request_id": request_id})

    # ── assessment outcome ─────────────────────────────────────────────────
    def track_recommendation(
        self, request_id: str, recommendation: str, partial_output: bool
    ) -> None:
        self._c_assessment.add(
            1,
            {
                "request_id": request_id,
                "recommendation": recommendation,
                "partial_output": partial_output,
            },
        )

    # ── AI / LLM observability ─────────────────────────────────────────────
    def track_llm_tokens(
        self, request_id: str, node_name: str, prompt_tokens: int, completion_tokens: int
    ) -> None:
        attrs = {"request_id": request_id, "node_name": node_name}
        self._h_prompt.record(prompt_tokens, attrs)
        self._h_completion.record(completion_tokens, attrs)

        # GenAI span (OTel semantic conventions) — makes per-call token usage a
        # first-class, queryable trace in Dynatrace AI observability.
        span = self._tracer.start_span(f"chat {node_name}")
        span.set_attribute("gen_ai.system", _GEN_AI_SYSTEM)
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", _model_name())
        span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
        span.set_attribute("request_id", request_id)
        span.set_attribute("node_name", node_name)
        span.end()

    def track_cost_per_assessment(
        self, request_id: str, prompt_tokens: int, completion_tokens: int
    ) -> None:
        cost = compute_cost(prompt_tokens, completion_tokens)
        self._h_cost.record(cost, {"request_id": request_id})

    # ── external dependency latency ────────────────────────────────────────
    def track_tavily_latency(self, request_id: str, duration_ms: float) -> None:
        self._h_tavily.record(duration_ms, {"request_id": request_id})

    def track_search_latency(self, request_id: str, duration_ms: float) -> None:
        self._h_search.record(duration_ms, {"request_id": request_id})


@asynccontextmanager
async def node_span(tracker: OtelTracker, request_id: str, node_name: str, partial_output: bool):
    """Wraps a graph node: opens an OTel span for the node and records its
    duration as a metric on exit (even if the node raises)."""
    span = tracker._tracer.start_span(f"node {node_name}")
    span.set_attribute("request_id", request_id)
    span.set_attribute("node_name", node_name)
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = (time.monotonic() - start) * 1000
        span.set_attribute("partial_output", partial_output)
        span.end()
        tracker.track_node_duration(request_id, node_name, elapsed, partial_output)


# ── global init + singleton ────────────────────────────────────────────────

_tracker_singleton: "OtelTracker | None" = None


def init_telemetry() -> bool:
    """Configure global OTel providers to export to Dynatrace over OTLP.

    Returns True if a Dynatrace exporter was wired (DT_ENV_URL + DT_API_TOKEN
    present), False if telemetry runs in no-op mode (local/dev, tests, CI).
    """
    env_url = os.environ.get("DT_ENV_URL", "").rstrip("/")
    api_token = os.environ.get("DT_API_TOKEN", "")
    if not env_url or not api_token:
        return False

    # Lazy import so the http exporter is only required when actually exporting.
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "procureiq-backend"),
            "service.namespace": "procureiq",
            "deployment.environment": os.environ.get("ENVIRONMENT", "prod"),
        }
    )
    headers = {"Authorization": f"Api-Token {api_token}"}
    otlp_base = f"{env_url}/api/v2/otlp"

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_base}/v1/traces", headers=headers))
    )
    trace.set_tracer_provider(tracer_provider)

    # Dynatrace OTLP metric ingest requires DELTA temporality (cumulative → 400).
    delta_temporality = {
        Counter: AggregationTemporality.DELTA,
        Histogram: AggregationTemporality.DELTA,
    }
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=f"{otlp_base}/v1/metrics",
            headers=headers,
            preferred_temporality=delta_temporality,
        )
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
    return True


def get_tracker() -> "OtelTracker":
    global _tracker_singleton
    if _tracker_singleton is None:
        _tracker_singleton = OtelTracker()
    return _tracker_singleton


def _extract_request_id(scope: dict) -> str:
    for key, value in scope.get("headers", []):
        if key == b"x-request-id":
            return value.decode()
    return ""


class RequestLatencyMiddleware:
    def __init__(self, app, tracker: OtelTracker):
        self._app = app
        self._tracker = tracker

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = _extract_request_id(scope)
        start = time.monotonic()
        try:
            await self._app(scope, receive, send)
        finally:
            elapsed = (time.monotonic() - start) * 1000
            self._tracker.track_request_latency(request_id, elapsed)
