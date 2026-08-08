"""
Pipeline RAG complet : question -> identification du document pertinent
(recherche vectorielle fine) -> reconstitution du document entier comme
contexte -> génération de réponse avec citation des sources.
"""
import os
import sys

import psycopg2
import requests
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

load_dotenv()

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
GENERATION_MODEL = "llama3.1:8b"
TOP_DOCS = 1

RAG_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Tu es un assistant pour des analystes fraude dans une banque. "
        "Réponds en te basant uniquement sur le contexte fourni par l'utilisateur. "
        "Si le contexte contient une procédure avec plusieurs étapes numérotées, "
        "tu DOIS restituer TOUTES les étapes, de la première à la dernière, sans "
        "en omettre aucune, même si la question semble générale. Reprends "
        "fidèlement les chiffres, seuils et délais exacts du contexte pour chaque "
        "étape. Si l'information demandée n'est pas dans le contexte, réponds "
        "exactement : \"Je ne sais pas, cette information n'est pas dans les "
        "documents fournis.\""
    ),
    (
        "human",
        "Contexte :\n{context}\n\nQuestion : {question}"
    ),
])


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def embed_text(text: str, is_query: bool = False) -> list[float]:
    prefix = "search_query: " if is_query else "search_document: "
    response = requests.post(OLLAMA_EMBED_URL, json={"model": EMBEDDING_MODEL, "prompt": prefix + text}, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]


def retrieve_relevant_documents(question: str, top_docs: int = TOP_DOCS) -> list[dict]:
    """Identifie les documents pertinents via recherche fine (au niveau chunk),
    puis récupère chaque document dans son intégralité -- pour garantir que toutes
    les étapes d'une procédure séquentielle soient présentes dans le contexte,
    plutôt que de risquer de fragmenter une liste entre chunks isolés."""
    query_embedding = embed_text(question, is_query=True)
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT document_name, MIN(embedding <=> %s::vector) AS best_distance
                FROM rag.compliance_chunks
                GROUP BY document_name
                ORDER BY best_distance ASC
                LIMIT %s
                """,
                (embedding_str, top_docs),
            )
            relevant_docs = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT document_name, chunk_index, content
                FROM rag.compliance_chunks
                WHERE document_name = ANY(%s)
                ORDER BY document_name, chunk_index
                """,
                (relevant_docs,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    documents: dict[str, list[str]] = {}
    for doc_name, _, content in rows:
        documents.setdefault(doc_name, []).append(content)

    return [{"document": doc, "content": "\n".join(chunks)} for doc, chunks in documents.items()]


def format_context(docs: list[dict]) -> str:
    return "\n\n".join(f"[Source: {d['document']}]\n{d['content']}" for d in docs)


def answer_question(question: str) -> tuple[str, str]:
    docs = retrieve_relevant_documents(question)
    context = format_context(docs)

    llm = ChatOllama(model=GENERATION_MODEL, temperature=0, num_ctx=8192)
    chain = RAG_PROMPT | llm | StrOutputParser()

    answer = chain.invoke({"context": context, "question": question})
    return answer, context


if __name__ == "__main__":
    from groundedness_check import check_groundedness

    question = sys.argv[1] if len(sys.argv) > 1 else "Un client conteste un blocage de compte, que dois-je faire ?"
    print(f"Question : {question}\n")

    answer, context = answer_question(question)
    print("=== CONTEXTE ENVOYÉ AU MODÈLE ===")
    print(context)
    print("===================================\n")
    print(answer)

    check = check_groundedness(context, answer)
    if check["coverage_ratio"] is None:
        print("\n[Contrôle qualité] Aucun fait chiffré détecté dans le contexte -- rien à vérifier automatiquement.")
    else:
        print(f"\n[Contrôle qualité] Couverture des faits chiffrés du contexte : {check['coverage_ratio']:.0%}")
        if check["missing_from_answer"]:
            print(f"[ATTENTION] Faits présents dans le contexte mais absents de la réponse : {check['missing_from_answer']}")
