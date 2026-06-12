import os

import httpx

_SEARCH_URL = "https://api.tavily.com/search"


async def tavily_search(query: str, *, timeout: float = 15.0) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            _SEARCH_URL,
            json={"api_key": api_key, "query": query, "max_results": 5},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
