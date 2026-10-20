import os
import time

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI, RateLimitError

INDEX_NAME = "member-support"

# Cap total retry wait below the App Service 230s request timeout.
RATE_LIMIT_RETRIES = 4
RATE_LIMIT_BASE_WAIT = 2.0  # seconds; exponential backoff

SYSTEM_PROMPT = (
    "You are a member support assistant for a financial institution.\n"
    "Answer only based on the [Reference Material] below.\n"
    'If the material has no answer, do not guess; respond:\n'
    '"We could not confirm the information. For accurate guidance, please\n'
    'contact the customer center (phone/email)."\n'
    "Always append the reference numbers used at the end in the format [Sources: 1, 3]."
)


class RAG:
    def __init__(self):
        self.search_client = SearchClient(
            os.environ["AZURE_SEARCH_ENDPOINT"],
            INDEX_NAME,
            AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]),
        )
        self.openai_client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_KEY"],
            api_version="2024-06-01",
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            # Fail fast on upstream hangs/429 instead of blocking the worker
            # (SDK default is 600s timeout + 2 retries); _retry handles backoff.
            timeout=30.0,
            max_retries=0,
        )
        self.embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
        self.chat_deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")

    def _retry(self, fn):
        for attempt in range(RATE_LIMIT_RETRIES):
            try:
                return fn()
            except RateLimitError:
                wait = RATE_LIMIT_BASE_WAIT * (2**attempt)
                print(f"rate limited, retrying in {wait:.1f}s", flush=True)
                time.sleep(wait)
        raise RuntimeError("Azure OpenAI rate limit persisted after retries")

    def embed_query(self, text):
        response = self._retry(
            lambda: self.openai_client.embeddings.create(
                model=self.embedding_deployment, input=[text]
            )
        )
        return response.data[0].embedding

    def hybrid_search(self, question, top_k=5):
        vector = self.embed_query(question)
        results = self.search_client.search(
            search_text=question,
            vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=top_k, fields="content_vector")],
            top=top_k,
            select=["id", "content", "title", "source_url", "category", "chunk_id"],
        )
        return [dict(r) for r in results]

    def generate(self, question):
        chunks = self.hybrid_search(question)
        context = "\n".join(
            f"[{i}] (title: {c['title']}) (URL: {c['source_url']}) content: {c['content']}"
            for i, c in enumerate(chunks, start=1)
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"[Reference Material]\n{context}\n\nQuestion: {question}"},
        ]
        response = self._retry(
            lambda: self.openai_client.chat.completions.create(
                model=self.chat_deployment,
                messages=messages,
                temperature=0,
                max_tokens=500,
            )
        )
        answer = response.choices[0].message.content
        sources = [
            {"title": c["title"], "url": c["source_url"], "chunk_id": c["chunk_id"]}
            for c in chunks
        ]
        return {"answer": answer, "sources": sources}
