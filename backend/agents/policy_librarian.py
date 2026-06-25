import os
import time

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI, OpenAIError

from observability import get_tracker, node_span
from state import NodeError, PolicyHit, State, infer_severity

_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
_KEY = os.environ.get("AZURE_SEARCH_API_KEY", "")
_INDEX = os.environ.get("AZURE_SEARCH_INDEX_NAME", "procureiq-policy")

_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_OPENAI_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
_EMBEDDING_DEPLOYMENT = os.environ.get(
    "AZURE_OPENAI_DEPLOYMENT_EMBEDDING", "text-embedding-3-small"
)
_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")

# Must match ingest.py index field "embedding" and its 1536 dims.
_VECTOR_FIELD = "embedding"
_TOP_K = 5


async def _embed_query(text: str) -> list[float]:
    """Embed query text with the same model used at ingest, for vector retrieval."""
    client = AsyncAzureOpenAI(
        azure_endpoint=_OPENAI_ENDPOINT,
        api_key=_OPENAI_KEY,
        api_version=_OPENAI_API_VERSION,
    )
    async with client:
        response = await client.embeddings.create(input=[text], model=_EMBEDDING_DEPLOYMENT)
        return response.data[0].embedding


async def search_policy_chunks(category: str, query: str) -> list[dict]:
    # Semantic retrieval (PRD Story 16): embed the query and run pure vector
    # search against the HNSW index. @search.score is cosine-based (~0-1), which
    # the Slice 5 audit criterion (score > 0.7) depends on. Do NOT fall back to
    # lexical search_text — that reintroduces keyword-matching and unbounded scores.
    vector = await _embed_query(query)
    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=_TOP_K,
        fields=_VECTOR_FIELD,
    )
    credential = AzureKeyCredential(_KEY)
    async with SearchClient(_ENDPOINT, _INDEX, credential) as client:
        results = await client.search(
            search_text=None,
            vector_queries=[vector_query],
            top=_TOP_K,
        )
        hits = []
        async for r in results:
            hits.append({
                "chunk_text": r["chunk_text"],
                "score": r["@search.score"],
                "source_doc": r["source_doc"],
            })
        return hits


async def policy_librarian_node(state: State) -> dict:
    tracker = get_tracker()
    request_id = state["request_id"]
    category = state["category"]
    query = f"{category} risk policy compliance requirements"

    async with node_span(tracker, request_id, "policy_librarian", state["partial_output"]):
        t0 = time.monotonic()
        try:
            hits_raw = await search_policy_chunks(category, query)
        except (ResourceNotFoundError, ServiceRequestError, OpenAIError) as exc:
            # Search down OR query-embedding failed → soft-fail, do not crash the graph.
            error: NodeError = {
                "node": "policy_librarian",
                "reason": f"search_unavailable:{type(exc).__name__}",
                "fallback_used": True,
            }
            return {
                "policy_hits": [],
                "errors": list(state["errors"]) + [error],
                "partial_output": True,
            }
        tracker.track_search_latency(request_id, (time.monotonic() - t0) * 1000)

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
