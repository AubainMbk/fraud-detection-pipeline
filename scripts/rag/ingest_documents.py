"""
Ingestion des documents de compliance : découpage en chunks, vectorisation
via Ollama (nomic-embed-text), stockage dans pgvector.
"""
import os
import re
import glob
import logging

import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
DOCS_DIR = "data/compliance_docs"


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def chunk_document(text: str) -> list[str]:
    """Découpe un document en chunks fins. Chaque item d'une liste numérotée
    devient un chunk séparé pour éviter la dilution d'embedding d'un gros bloc."""
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    list_item_pattern = re.compile(r'^\d+\.\s')
    chunks = []

    for para in raw_paragraphs:
        lines = [l.strip() for l in para.split("\n")]
        if list_item_pattern.match(lines[0]):
            current = []
            for line in lines:
                if list_item_pattern.match(line) and current:
                    chunks.append(" ".join(current))
                    current = [line]
                else:
                    current.append(line)
            if current:
                chunks.append(" ".join(current))
        else:
            chunks.append(" ".join(lines))

    return [c for c in chunks if len(c) > 40 and not c.startswith("#")]


def embed_text(text: str, is_query: bool = False) -> list[float]:
    """nomic-embed-text exige un préfixe de tâche pour un alignement correct
    de l'espace vectoriel en recherche asymétrique (query courte / doc long)."""
    prefix = "search_query: " if is_query else "search_document: "
    response = requests.post(
        OLLAMA_URL,
        json={"model": EMBEDDING_MODEL, "prompt": prefix + text},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def extract_title(text: str) -> str:
    """Récupère la première ligne de titre markdown (# ...), ou un nom par défaut."""
    for line in text.split("\n"):
        if line.strip().startswith("#"):
            return line.strip().lstrip("#").strip()
    return ""


def main():
    conn = get_pg_connection()
    total_chunks = 0

    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE rag.compliance_chunks RESTART IDENTITY")
        conn.commit()

        for filepath in glob.glob(os.path.join(DOCS_DIR, "*.md")):
            document_name = os.path.basename(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            title = extract_title(text)
            chunks = chunk_document(text)
            logger.info(f"{document_name} -> {len(chunks)} chunks (titre: '{title}')")

            for i, chunk in enumerate(chunks):
                # Le titre enrichit UNIQUEMENT le texte utilisé pour l'embedding
                # (meilleur ancrage sémantique), jamais le contenu stocké/affiché.
                text_for_embedding = f"{title}. {chunk}" if title else chunk
                embedding = embed_text(text_for_embedding, is_query=False)
                embedding_str = "[" + ",".join(map(str, embedding)) + "]"

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO rag.compliance_chunks
                            (document_name, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s::vector)
                        """,
                        (document_name, i, chunk, embedding_str),
                    )
                conn.commit()
                total_chunks += 1

        logger.info(f"Ingestion terminée : {total_chunks} chunks vectorisés.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()