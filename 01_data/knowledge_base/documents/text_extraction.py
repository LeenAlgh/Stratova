import fitz  # PyMuPDF
import json
import os
import json
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv
from openai import OpenAI
#pip install sentence-transformers chromadb
#pip install openai
#pip install python-dotenv

def extract_pdf(file_path):
    doc = fitz.open(file_path)
    results = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        results.append({
            "doc_id": os.path.basename(file_path),
            "page": page_num + 1,
            "content": text.strip()
        })

    return results

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text

file_path = os.path.join("knowledge_base", "documents", "Beam_Data.pdf")

data = extract_pdf(file_path)

for item in data:
    item["content"] = clean_text(item["content"])

def chunk_text(text, chunk_size=100, overlap=15):
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
        
    return chunks

chunked_data = []

for item in data:

    chunks = chunk_text(item["content"])

    for idx, chunk in enumerate(chunks):

        chunked_data.append({
            "doc_id": item["doc_id"],
            "page": item["page"],
            "chunk_id": f"p{item['page']}_c{idx}",
            "content": chunk
        })

with open("chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunked_data, f, ensure_ascii=False, indent=2)

model = SentenceTransformer("all-MiniLM-L6-v2")

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(DOCS_DIR, "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_or_create_collection("pdf_kb")

chunks = chunked_data

ids = []
documents = []
metadatas = []
embeddings = []

for i, chunk in enumerate(chunks):
    text = chunk["content"]

    ids.append(str(i))
    documents.append(text)
    metadatas.append({
        "doc_id": chunk["doc_id"],
        "page": chunk["page"],
        "chunk_id": chunk["chunk_id"]
    })
    embeddings.append(model.encode(text).tolist())
"""
#add a guardrail to delete duplicates
try:
    chroma_client.delete_collection("pdf_kb")
except:
    pass
"""
collection = chroma_client.get_or_create_collection("pdf_kb")
collection.add(
    ids=ids,
    documents=documents,
    metadatas=metadatas,
    embeddings=embeddings
)
query = "What is BeamData AI Hub?"

query_embedding = model.encode(query).tolist()

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

for i, doc in enumerate(results["documents"][0]):
    print(f"\nResult {i+1}")
    print("Metadata:", results["metadatas"][0][i])
    print("Text:", doc)

query = "what is beam analysis?"

query_embedding = model.encode(query).tolist()
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

for doc in results["documents"][0]:
    print("=" * 50)
    print(doc)

def query_kb(question, top_k=3):

    query_vector = model.encode(question).tolist()

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k
    )

    return results

def show_kb_answer(question):

    results = query_kb(question)

    print("Top relevant chunks:\n")

    for i, doc in enumerate(results["documents"][0]):
        print("=" * 50)
        print(f"Chunk {i+1}")
        print(doc)

show_kb_answer("what is beamdata?")
show_kb_answer("Who are beamdata clients?")

load_dotenv() 

openai_client = OpenAI(api_key=os.getenv("openai_key"))

def build_context(chunks):
    context_parts = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        context_parts.append(
            f"[Source: {meta['doc_id']} | Page {meta['page']}]\n{doc}"
        )
    return "\n\n".join(context_parts)

def generate_answer(question):

    # 1. Retrieve from KB
    results = query_kb(question)
    chunks = results["documents"][0]  # extract the actual strings
    context = build_context(results)

    # 2. Call LLM
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You are a precise assistant.
Answer ONLY using the provided context.
If the answer is not in the context, say: "I don't know based on the provided documents."
"""
            },
            {
                "role": "user",
                "content": f"""
Context:
{context}

Question:
{question}
"""
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

question = "what is beam theory?"

answer = generate_answer(question)

print(answer)
