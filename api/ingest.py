#!/usr/bin/env python3
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import tiktoken
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    VectorSearch,
    VectorSearchProfile,
)
from openai import AzureOpenAI, RateLimitError

INDEX_NAME = "member-support"
CHUNK_SIZE_TOKENS = 500
OVERLAP_TOKENS = 50
EMBEDDING_BATCH = 2
VECTOR_DIMENSIONS = 1536
SOURCE_BASE_URL = "https://www.examplefinancial.com"


def require_env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"missing environment variable: {name}")
    return value


def load_documents(data_dir):
    documents = []
    for path in sorted(data_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        lines = text.split("\n")
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            body = "\n".join(lines[1:]).strip()
        else:
            title = path.stem.replace("-", " ").title()
            body = text
        documents.append(
            {
                "title": title,
                "body": body,
                "category": path.parent.name,
                "source_url": f"{SOURCE_BASE_URL}/{path.parent.name}/{path.stem}",
            }
        )
    return documents


def chunk_text(text, tokenizer):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_len = 0
    for para in paragraphs:
        para_len = len(tokenizer.encode(para))
        if current and current_len + para_len > CHUNK_SIZE_TOKENS:
            chunks.append("\n\n".join(current))
            current = _overlap_tail(current, tokenizer)
            current_len = sum(len(tokenizer.encode(p)) for p in current)
        current.append(para)
        current_len += para_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _overlap_tail(paras, tokenizer):
    tail = []
    length = 0
    for para in reversed(paras):
        para_len = len(tokenizer.encode(para))
        if length + para_len > OVERLAP_TOKENS:
            break
        tail.insert(0, para)
        length += para_len
    return tail


def build_index(vector):
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="source_url", type=SearchFieldDataType.String, retrievable=True),
        SearchField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="chunk_id", type=SearchFieldDataType.Int32, retrievable=True),
        SearchField(name="last_updated", type=SearchFieldDataType.DateTimeOffset, sortable=True, filterable=True),
    ]
    vector_search = None
    if vector:
        fields.append(
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=VECTOR_DIMENSIONS,
                vector_search_profile_name="hnsw-profile",
            )
        )
        vector_search = VectorSearch(
            profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-algo")],
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
        )
    return SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)


def create_index(client, vector):
    try:
        client.create_or_update_index(build_index(vector))
        return True
    except Exception as exc:
        print(f"index creation failed (vector={vector}): {exc}")
        return False


def embed_batches(client, deployment, texts):
    embeddings = []
    for start in range(0, len(texts), EMBEDDING_BATCH):
        batch = texts[start : start + EMBEDDING_BATCH]
        for attempt in range(6):
            try:
                response = client.embeddings.create(model=deployment, input=batch)
                embeddings.extend(item.embedding for item in response.data)
                break
            except RateLimitError:
                wait = 60 * (attempt + 1)
                print(f"rate limited, retrying in {wait}s")
                time.sleep(wait)
        else:
            raise RuntimeError("embedding rate limit persisted after retries")
        print(f"embedded {min(start + EMBEDDING_BATCH, len(texts))}/{len(texts)}")
        time.sleep(2)
    return embeddings


def main():
    search_endpoint = require_env("AZURE_SEARCH_ENDPOINT")
    search_key = require_env("AZURE_SEARCH_KEY")
    openai_endpoint = require_env("AZURE_OPENAI_ENDPOINT")
    openai_key = require_env("AZURE_OPENAI_KEY")
    embedding_deployment = require_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

    data_dir = Path(__file__).resolve().parent.parent / "data"
    documents = load_documents(data_dir)
    print(f"loaded {len(documents)} documents")

    tokenizer = tiktoken.get_encoding("cl100k_base")
    chunks = []
    for doc in documents:
        for chunk_idx, chunk in enumerate(chunk_text(doc["body"], tokenizer)):
            chunks.append({"doc": doc, "chunk": chunk, "chunk_idx": chunk_idx})
    print(f"produced {len(chunks)} chunks")

    index_client = SearchIndexClient(search_endpoint, AzureKeyCredential(search_key))
    vector_enabled = create_index(index_client, vector=True)
    if not vector_enabled:
        print("falling back to keyword-only index")
        if not create_index(index_client, vector=False):
            sys.exit("could not create the search index")

    embeddings = None
    if vector_enabled:
        openai_client = AzureOpenAI(
            api_key=openai_key,
            api_version="2024-06-01",
            azure_endpoint=openai_endpoint,
        )
        embeddings = embed_batches(openai_client, embedding_deployment, [c["chunk"] for c in chunks])

    now = datetime.now(timezone.utc).isoformat()
    to_upload = []
    for position, item in enumerate(chunks):
        doc, chunk, chunk_idx = item["doc"], item["chunk"], item["chunk_idx"]
        document = {
            "id": f"{hashlib.sha256(chunk.encode()).hexdigest()[:16]}-{chunk_idx}",
            "content": chunk,
            "title": doc["title"],
            "source_url": doc["source_url"],
            "category": doc["category"],
            "chunk_id": chunk_idx,
            "last_updated": now,
        }
        if vector_enabled:
            document["content_vector"] = embeddings[position]
        to_upload.append(document)

    search_client = SearchClient(search_endpoint, INDEX_NAME, AzureKeyCredential(search_key))
    result = search_client.upload_documents(to_upload)
    succeeded = sum(1 for r in result if r.succeeded)
    print(f"uploaded {len(to_upload)} documents ({succeeded} succeeded)")


if __name__ == "__main__":
    main()
