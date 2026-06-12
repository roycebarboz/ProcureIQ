from datetime import datetime, timezone

from state import MarketSignal

_FIXTURE: dict[str, dict] = {
    "Acme Corp": {
        "content": "3 years on-time delivery; $2.1M annual spend",
        "confidence": 0.95,
    },
    "Globex": {
        "content": "$500K annual spend; 2 late deliveries in 2024",
        "confidence": 0.80,
    },
}


def get_erp_spend(vendor_name: str) -> MarketSignal:
    entry = _FIXTURE.get(vendor_name)
    if entry:
        return MarketSignal(
            source="erp",
            content=entry["content"],
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            confidence=entry["confidence"],
        )
    return MarketSignal(
        source="erp",
        content="",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        confidence=0.0,
    )
