import os
import time
from contextlib import asynccontextmanager

from applicationinsights import TelemetryClient

# Azure OpenAI GPT-4o pricing per 1K tokens
_PROMPT_COST_PER_1K = 0.005
_COMPLETION_COST_PER_1K = 0.015


def compute_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        (prompt_tokens / 1000) * _PROMPT_COST_PER_1K
        + (completion_tokens / 1000) * _COMPLETION_COST_PER_1K,
        6,
    )


class AppInsightsTracker:
    def __init__(self, client=None):
        self._client = client

    def _send_metric(self, name: str, value: float, properties: dict) -> None:
        if self._client is None:
            return
        self._client.track_metric(name, value, properties=properties)

    def _send_event(self, name: str, properties: dict) -> None:
        if self._client is None:
            return
        self._client.track_event(name, properties=properties)

    def track_node_duration(
        self,
        request_id: str,
        node_name: str,
        duration_ms: float,
        partial_output: bool,
    ) -> None:
        self._send_metric(
            "node_duration_ms",
            duration_ms,
            {
                "request_id": request_id,
                "node_name": node_name,
                "partial_output": str(partial_output),
            },
        )

    def track_recommendation(
        self,
        request_id: str,
        recommendation: str,
        partial_output: bool,
    ) -> None:
        self._send_event(
            "assessment_complete",
            properties={
                "request_id": request_id,
                "recommendation": recommendation,
                "partial_output": str(partial_output),
            },
        )

    def track_llm_tokens(
        self,
        request_id: str,
        node_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        props = {"request_id": request_id, "node_name": node_name}
        self._send_metric("llm_prompt_tokens", prompt_tokens, props)
        self._send_metric("llm_completion_tokens", completion_tokens, props)

    def track_tavily_latency(self, request_id: str, duration_ms: float) -> None:
        self._send_metric("tavily_latency_ms", duration_ms, {"request_id": request_id})

    def track_search_latency(self, request_id: str, duration_ms: float) -> None:
        self._send_metric("search_latency_ms", duration_ms, {"request_id": request_id})

    def track_cost_per_assessment(
        self,
        request_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        cost = compute_cost(prompt_tokens, completion_tokens)
        self._send_metric("cost_per_assessment_usd", cost, {"request_id": request_id})


@asynccontextmanager
async def node_span(
    tracker: AppInsightsTracker,
    request_id: str,
    node_name: str,
    partial_output: bool,
):
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = (time.monotonic() - start) * 1000
        tracker.track_node_duration(request_id, node_name, elapsed, partial_output)


_tracker_singleton: "AppInsightsTracker | None" = None


def get_tracker() -> "AppInsightsTracker":
    global _tracker_singleton
    if _tracker_singleton is None:
        ikey = os.environ.get("APPINSIGHTS_INSTRUMENTATIONKEY", "")
        client = TelemetryClient(ikey) if ikey else None
        _tracker_singleton = AppInsightsTracker(client=client)
    return _tracker_singleton


def _extract_request_id(scope: dict) -> str:
    for key, value in scope.get("headers", []):
        if key == b"x-request-id":
            return value.decode()
    return ""


class RequestLatencyMiddleware:
    def __init__(self, app, tracker: AppInsightsTracker):
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
            self._tracker._send_metric(
                "request_latency_ms",
                elapsed,
                {"request_id": request_id},
            )
