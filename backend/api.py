import json
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from graph import graph
from state import State, compute_confidence

app = FastAPI(title="ProcureIQ")

_results: dict[str, State] = {}


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
        async for chunk in graph.astream(initial_state, stream_mode="updates"):
            node_name = next(iter(chunk))
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

    return EventSourceResponse(event_generator())


@app.get("/assess/{request_id}/result")
async def get_result(request_id: str):
    if request_id not in _results:
        raise HTTPException(status_code=404, detail="Result not found")
    return _results[request_id]
