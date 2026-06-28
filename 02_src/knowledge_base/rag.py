"""Shared RAG helpers for all Stratova agents."""

import os

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI

from project_paths import CHROMA_DIR, ENV_PATH, KB_DOCS_DIR

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = str(CHROMA_DIR)
load_dotenv(ENV_PATH, override=True)


print("ENV_PATH =", ENV_PATH)
print("OPENAI KEY FOUND =", bool(os.getenv("OPENAI_API_KEY")))

_model = None
_openai_client = None

DEFAULT_TOP_K = 5
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
COLLECTION_NAME = "pdf_kb"


def reset_kb_cache():
    """Clear cached clients. Safe to call before each agent run in notebooks."""
    global _model, _openai_client
    _model = None
    _openai_client = None


def _ensure_collection_populated():
    """Load chunks into Chroma when the collection is missing or empty."""
    from knowledge_base.rebuild_chroma import rebuild_chroma

    rebuild_chroma(force=True)


def _open_collection():
    """Always open a fresh Chroma handle (avoids stale notebook kernel caches)."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        collection = client.get_collection(COLLECTION_NAME)
        if collection.count() == 0:
            _ensure_collection_populated()
            client = chromadb.PersistentClient(path=CHROMA_DIR)
            collection = client.get_collection(COLLECTION_NAME)
        return collection
    except chromadb.errors.NotFoundError:
        _ensure_collection_populated()
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        return client.get_collection(COLLECTION_NAME)


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("openai_key")
        if not api_key:
            raise ValueError("Set OPENAI_API_KEY or openai_key in .env")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def query_kb(question: str, top_k: int = DEFAULT_TOP_K):
    model = _get_model()
    query_vector = model.encode(question).tolist()
    last_exc = None

    for _ in range(3):
        try:
            collection = _open_collection()
            return collection.query(query_embeddings=[query_vector], n_results=top_k)
        except chromadb.errors.NotFoundError as exc:
            last_exc = exc
            _ensure_collection_populated()
        except chromadb.errors.InternalError as exc:
            raise RuntimeError(
                "ChromaDB index is corrupted. Rebuild it with: "
                "python knowledge_base/rebuild_chroma.py"
            ) from exc

    raise RuntimeError(
        "ChromaDB query failed after retries. Rebuild with: "
        "python knowledge_base/rebuild_chroma.py"
    ) from last_exc


def retrieve_context(question: str, top_k: int = DEFAULT_TOP_K):
    results = query_kb(question, top_k)
    docs = results["documents"][0]
    metadata = results["metadatas"][0]
    context = "\n\n".join(docs)
    return context, metadata


def build_context(results) -> str:
    parts = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        parts.append(
            f"[Source: {meta['doc_id']} | Page {meta['page']} | Chunk {meta['chunk_id']}]\n{doc}"
        )
    return "\n\n".join(parts)


def retrieve_context_formatted(question: str, top_k: int = DEFAULT_TOP_K) -> str:
    return build_context(query_kb(question, top_k))


def ask_from_kb(prompt: str, top_k: int = DEFAULT_TOP_K) -> dict:
    context, metadata = retrieve_context(prompt, top_k)
    answer = ask_with_context(
        context=context,
        prompt=prompt,
        system=(
            "You are a GTM strategy assistant. Answer ONLY using the provided context. "
            "If the answer is not found in the context, say you could not find it in the knowledge base."
        ),
    )
    return {"answer": answer, "sources": metadata}


def ask_with_context(
    context: str,
    prompt: str,
    system: str = "You are an expert B2B go-to-market strategist.",
    temperature: float = 0.3,
) -> str:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\n---\n\nTask:\n{prompt}",
            },
        ],
    )
    return response.choices[0].message.content





"""client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)"""

def ask_llm(prompt):

    context, metadata = retrieve_context(prompt)

    full_prompt = f"""
You are a GTM strategy assistant.

Answer ONLY using the provided context.
If the answer is not found in the context, say:
'I could not find that information in the knowledge base.'

Context:
{context}

Question:
{prompt}
"""
    client = _get_openai_client()

    response = client.responses.create(
        model="gpt-5",
        input=full_prompt
    )

    return {
        "answer": response.output_text,
        "sources": metadata
    }

def ask_general_llm(prompt):
    response = llm.invoke(prompt)
    return response.content


load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.3
)