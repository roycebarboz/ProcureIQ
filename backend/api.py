import json
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from graph import graph
from observability import RequestLatencyMiddleware, get_tracker
from state import State, compute_confidence

app = FastAPI(title="ProcureIQ")
app.add_middleware(RequestLatencyMiddleware, tracker=get_tracker())

_results: dict[str, State] = {}
_result_timestamps: dict[str, str] = {}
_node_durations: dict[str, list[float]] = {}


class AssessRequest(BaseModel):
    vendor_name: str
    category: str
    spend_amount: Optional[float] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/assess")
async def assess(body: AssessRequest):
    request_id = str(uuid4())
    initial_state: State = {
        "request_id": request_id,
        "vendor_name": body.vendor_name,
        "spend_amount": body.spend_amount,
        "category": body.category,
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

    async def event_generator():
        current_state = dict(initial_state)
        prev_time = time.monotonic()
        async for chunk in graph.astream(initial_state, stream_mode="updates"):
            now = time.monotonic()
            node_name = next(iter(chunk))
            duration_ms = (now - prev_time) * 1000
            prev_time = now
            if node_name not in _node_durations:
                _node_durations[node_name] = []
            _node_durations[node_name].append(duration_ms)
            current_state.update(chunk[node_name])

            if node_name == "market_scout":
                yield {
                    "event": "scout_complete",
                    "data": json.dumps({
                        "request_id": request_id,
                        "market_data": current_state["market_data"],
                        "contract_flags": current_state["contract_flags"],
                        "errors": current_state["errors"],
                        "partial_output": current_state["partial_output"],
                    }),
                }
            elif node_name == "policy_librarian":
                yield {
                    "event": "librarian_complete",
                    "data": json.dumps({
                        "request_id": request_id,
                        "policy_hits": current_state["policy_hits"],
                        "errors": current_state["errors"],
                        "partial_output": current_state["partial_output"],
                    }),
                }
            elif node_name in ("risk_synthesizer", "human_review"):
                current_state["confidence"] = compute_confidence(current_state)
                yield {
                    "event": "assessment_complete",
                    "data": json.dumps({
                        "request_id": request_id,
                        "risk_score": current_state["risk_score"],
                        "confidence": current_state["confidence"],
                        "recommendation": current_state["recommendation"],
                        "risk_brief": current_state["risk_brief"],
                    }),
                }

        _results[request_id] = current_state
        _result_timestamps[request_id] = datetime.now(timezone.utc).isoformat()

    return EventSourceResponse(event_generator())


@app.get("/assess/{request_id}/result")
async def get_result(request_id: str):
    if request_id not in _results:
        raise HTTPException(status_code=404, detail="Result not found")
    return _results[request_id]


@app.get("/dashboard")
async def dashboard():
    assessments = list(_results.values())
    total = len(assessments)

    partial_count = sum(1 for a in assessments if a["partial_output"])
    partial_rate = round(partial_count / total * 100, 1) if total > 0 else 0.0

    recommendation_dist: dict[str, int] = {"Approve": 0, "Escalate": 0, "Reject": 0, "Pending": 0}
    for a in assessments:
        rec = a.get("recommendation", "Pending")
        if rec in recommendation_dist:
            recommendation_dist[rec] += 1

    node_latency = {
        node: round(sum(durations) / len(durations), 1)
        for node, durations in _node_durations.items()
        if durations
    }

    recent = sorted(
        [
            {
                "request_id": a["request_id"],
                "vendor_name": a["vendor_name"],
                "recommendation": a["recommendation"],
                "confidence": a["confidence"],
                "timestamp": _result_timestamps.get(a["request_id"], ""),
            }
            for a in assessments
        ],
        key=lambda x: x["timestamp"],
        reverse=True,
    )[:10]

    return {
        "node_latency": node_latency,
        "partial_rate": partial_rate,
        "recommendation_dist": recommendation_dist,
        "recent_assessments": recent,
    }
