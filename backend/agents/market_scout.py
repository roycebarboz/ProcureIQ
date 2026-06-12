import asyncio
from datetime import datetime, timezone

from state import MarketSignal, NodeError, State
from tools.erp_mock import get_erp_spend
from tools.tavily import tavily_search

_TIMEOUT = 15.0
_MAX_RETRIES = 1


async def market_scout_node(state: State) -> dict:
    vendor = state["vendor_name"]

    web_signal: MarketSignal | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            results = await asyncio.wait_for(tavily_search(vendor), timeout=_TIMEOUT)
            if results:
                web_signal = MarketSignal(
                    source="web_search",
                    content=results[0].get("content", ""),
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    confidence=float(results[0].get("score", 0.5)),
                )
            break
        except asyncio.TimeoutError:
            if attempt < _MAX_RETRIES:
                continue
            error: NodeError = {
                "node": "market_scout",
                "reason": "timeout_tavily",
                "fallback_used": True,
            }
            return {
                "market_data": [],
                "errors": list(state["errors"]) + [error],
                "partial_output": True,
            }

    erp_signal = get_erp_spend(vendor)
    signals: list[MarketSignal] = [erp_signal]
    if web_signal:
        signals.append(web_signal)

    return {
        "market_data": signals,
        "errors": list(state["errors"]),
        "partial_output": False,
    }
