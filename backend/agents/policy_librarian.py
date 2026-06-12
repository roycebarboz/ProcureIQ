import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient

from state import NodeError, PolicyHit, State, infer_severity

_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
_KEY = os.environ.get("AZURE_SEARCH_API_KEY", "")
_INDEX = os.environ.get("AZURE_SEARCH_INDEX_NAME", "procureiq-policy")


async def search_policy_chunks(category: str, query: str) -> list[dict]:
    credential = AzureKeyCredential(_KEY)
    async with SearchClient(_ENDPOINT, _INDEX, credential) as client:
        results = await client.search(query, top=5)
        hits = []
        async for r in results:
            hits.append({
                "chunk_text": r["chunk_text"],
                "score": r["@search.score"],
                "source_doc": r["source_doc"],
            })
        return hits


async def policy_librarian_node(state: State) -> dict:
    category = state["category"]
    query = f"{category} risk policy compliance requirements"

    hits_raw = await search_policy_chunks(category, query)

    if not hits_raw:
        error: NodeError = {
            "node": "policy_librarian",
            "reason": "no_relevant_chunks_retrieved",
            "fallback_used": True,
        }
        return {
            "policy_hits": [],
            "errors": list(state["errors"]) + [error],
            "partial_output": True,
        }

    policy_hits: list[PolicyHit] = [
        PolicyHit(
            chunk_text=h["chunk_text"],
            score=h["score"],
            source_doc=h["source_doc"],
            risk_category=infer_severity(h["chunk_text"]),
        )
        for h in hits_raw
    ]

    return {
        "policy_hits": policy_hits,
        "errors": list(state["errors"]),
        "partial_output": False,
    }
