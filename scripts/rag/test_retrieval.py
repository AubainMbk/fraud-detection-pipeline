"""Test isolé de la recherche sémantique, sans génération LLM -- valide le retrieval seul."""
import os

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def embed_text(text: str) -> list[float]:
    response = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]


question = "Un client conteste un blocage de compte, que dois-je faire ?"

query_embedding = embed_text(question)
embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

conn = get_pg_connection()
with conn.cursor() as cur:
    # L'opérateur <=> calcule la distance cosinus : plus la valeur est proche de 0, plus c'est pertinent
    cur.execute(
        """
        SELECT document_name, content, embedding <=> %s::vector AS distance
        FROM rag.compliance_chunks
        ORDER BY distance ASC
        LIMIT 7
        """,
        (embedding_str,),
    )
    results = cur.fetchall()

print(f"Question : {question}\n")
for doc, content, distance in results:
    print(f"[{doc}] (distance={distance:.4f})")
    print(f"  {content[:150]}...\n")

conn.close()
