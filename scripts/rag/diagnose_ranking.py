"""Diagnostic : classement complet par document (pas par chunk) pour une question donnée."""
import os
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/embeddings"


def embed_text(text: str, is_query: bool = False) -> list[float]:
    prefix = "search_query: " if is_query else "search_document: "
    response = requests.post(OLLAMA_URL, json={"model": "nomic-embed-text", "prompt": prefix + text}, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]


question = "Quelle est la procédure d'escalade pour une fraude de 60000 euros ?"
embedding_str = "[" + ",".join(map(str, embed_text(question, is_query=True))) + "]"

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
    dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"), password=os.getenv("POSTGRES_PASSWORD"),
)
with conn.cursor() as cur:
    cur.execute(
        """
        SELECT document_name, MIN(embedding <=> %s::vector) AS best_distance
        FROM rag.compliance_chunks GROUP BY document_name ORDER BY best_distance ASC
        """,
        (embedding_str,),
    )
    for doc, dist in cur.fetchall():
        print(f"{doc}: {dist:.4f}")
conn.close()