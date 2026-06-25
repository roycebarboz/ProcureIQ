"""
Semantic chunking + Azure AI Search upsert for policy corpus.

Usage:
    python ingest.py

Reads .txt files from ../corpus/, splits on numbered section headers,
embeds via Azure OpenAI text-embedding-3-small, upserts to Azure AI Search.
"""

import hashlib
import os
import re
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
_SEARCH_KEY = os.environ["AZURE_SEARCH_API_KEY"]
_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "procureiq-policy")
_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
_OPENAI_KEY = os.environ["AZURE_OPENAI_API_KEY"]
_EMBEDDING_DEPLOYMENT = os.environ.get(
    "AZURE_OPENAI_DEPLOYMENT_EMBEDDING", "text-embedding-3-small"
)
_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")

_CORPUS_DIR = Path(__file__).parent.parent / "corpus"

# Matches numbered section headers like "1.", "2.1", "9.104-2", "APPENDIX A"
_SECTION_PATTERN = re.compile(
    r"^(?:\d+(?:\.\d+)*(?:-\d+)*[.\s]|APPENDIX\s+[A-Z]|CHAPTER\s+\d+|PART\s+[IVX]+)",
    re.MULTILINE,
)


def chunk_document(text: str, source_doc: str) -> list[dict]:
    """Split text on numbered section headers; yield dicts with id, chunk_text, source_doc."""
    positions = [m.start() for m in _SECTION_PATTERN.finditer(text)]
    if not positions:
        return [{"chunk_text": text.strip(), "source_doc": source_doc}]

    chunks = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        chunk_text = text[start:end].strip()
        if len(chunk_text) > 50:  # skip trivially short fragments
            chunks.append({"chunk_text": chunk_text, "source_doc": source_doc})
    return chunks


def embed_chunks(client: AzureOpenAI, chunks: list[dict]) -> list[dict]:
    texts = [c["chunk_text"] for c in chunks]
    response = client.embeddings.create(input=texts, model=_EMBEDDING_DEPLOYMENT)
    for chunk, item in zip(chunks, response.data):
        chunk["embedding"] = item.embedding
        chunk["id"] = hashlib.sha256(
            f"{chunk['source_doc']}::{chunk['chunk_text'][:100]}".encode()
        ).hexdigest()
    return chunks


def ensure_index(index_client: SearchIndexClient) -> None:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(
            name="chunk_text",
            type=SearchFieldDataType.String,
            searchable=True,
            retrievable=True,
        ),
        SimpleField(name="source_doc", type=SearchFieldDataType.String, retrievable=True),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            retrievable=False,
            vector_search_dimensions=1536,
            vector_search_profile_name="hnsw-profile",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw")],
    )
    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="chunk_text")]
                ),
            )
        ]
    )
    index = SearchIndex(
        name=_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )
    index_client.create_or_update_index(index)
    print(f"Index '{_INDEX_NAME}' ready.")


def main() -> None:
    openai_client = AzureOpenAI(
        azure_endpoint=_OPENAI_ENDPOINT,
        api_key=_OPENAI_KEY,
        api_version=_OPENAI_API_VERSION,
    )
    credential = AzureKeyCredential(_SEARCH_KEY)
    index_client = SearchIndexClient(_SEARCH_ENDPOINT, credential)
    search_client = SearchClient(_SEARCH_ENDPOINT, _INDEX_NAME, credential)

    ensure_index(index_client)

    corpus_files = sorted(_CORPUS_DIR.glob("*.txt"))
    if not corpus_files:
        raise FileNotFoundError(f"No .txt files found in {_CORPUS_DIR}")

    all_docs: list[dict] = []
    for path in corpus_files:
        text = path.read_text(encoding="utf-8")
        chunks = chunk_document(text, source_doc=path.name)
        print(f"  {path.name}: {len(chunks)} chunks")
        all_docs.extend(chunks)

    print(f"Embedding {len(all_docs)} chunks...")
    embedded = embed_chunks(openai_client, all_docs)

    batch_size = 100
    for i in range(0, len(embedded), batch_size):
        batch = embedded[i : i + batch_size]
        results = search_client.upload_documents(documents=batch)
        failed = [r for r in results if not r.succeeded]
        if failed:
            for f in failed:
                print(f"  FAILED: {f.key} — {f.error_message}")
        print(f"  Upserted batch {i // batch_size + 1}: {len(batch) - len(failed)} succeeded")

    print("Ingest complete.")


if __name__ == "__main__":
    main()
