"""Rebuild ChromaDB from chunks.json when the index is corrupted."""

import json
import os
import shutil

import chromadb
from sentence_transformers import SentenceTransformer

from project_paths import KB_DOCS_DIR

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = str(KB_DOCS_DIR)
CHROMA_DIR = os.path.join(DOCS_DIR, "chroma_db")
CHUNKS_PATH = os.path.join(DOCS_DIR, "chunks.json")
COLLECTION_NAME = "pdf_kb"


def rebuild_chroma(force: bool = True) -> int:
    if not os.path.exists(CHUNKS_PATH):
        raise FileNotFoundError(f"Missing {CHUNKS_PATH}. Run text extraction first.")

    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            if os.path.isdir(CHROMA_DIR):
                shutil.rmtree(CHROMA_DIR)
            client = chromadb.PersistentClient(path=CHROMA_DIR)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    collection = client.get_or_create_collection(COLLECTION_NAME)

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for i, chunk in enumerate(chunks):
        text = chunk["content"]
        ids.append(str(i))
        documents.append(text)
        metadatas.append(
            {
                "doc_id": chunk["doc_id"],
                "page": chunk["page"],
                "chunk_id": chunk["chunk_id"],
            }
        )
        embeddings.append(model.encode(text).tolist())

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    return len(chunks)


if __name__ == "__main__":
    count = rebuild_chroma()
    print(f"Rebuilt ChromaDB with {count} chunks at {CHROMA_DIR}")
