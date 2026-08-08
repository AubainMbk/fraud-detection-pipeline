"""
Pipeline text-to-SQL complet : question -> génération SQL (LLM) -> validation
(garde-fous) -> exécution (rôle lecture seule, timeout) -> réponse en langage naturel.
"""
import os
import sys

import psycopg2
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from schema_context import SCHEMA_DESCRIPTION
from sql_guardrails import validate_and_secure_sql, UnsafeQueryError

load_dotenv()

GENERATION_MODEL = "llama3.1:8b"
STATEMENT_TIMEOUT_MS = 5000

SQL_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Tu es un générateur de requêtes PostgreSQL. À partir du schéma fourni et "
        "d'une question en langage naturel, génère UNE SEULE requête SQL SELECT qui "
        "y répond. Réponds UNIQUEMENT avec le code SQL, sans explication, sans balises "
        "markdown, sans point-virgule final. N'utilise que les tables et colonnes du "
        "schéma fourni -- n'invente jamais de nom de colonne ou de table.\n\n"
        "Schéma disponible :\n{schema}"
    ),
    ("human", "{question}"),
])

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Tu es un assistant pour des analystes fraude. On te donne une question, la "
        "requête SQL exécutée, et son résultat. Réponds à la question en langage "
        "naturel, en te basant uniquement sur le résultat fourni. Si le résultat "
        "contient plusieurs lignes, tu DOIS toutes les lister, sans en omettre aucune, "
        "même si la question ne précise pas explicitement d'en donner le nombre exact."
    ),
    ("human", "Question : {question}\nRequête exécutée : {sql}\nRésultat : {result}"),
])


def get_readonly_connection():
    """Connexion dédiée avec le rôle en lecture seule -- couche de sécurité
    indépendante de toute validation applicative."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_READONLY_USER"),
        password=os.getenv("POSTGRES_READONLY_PASSWORD"),
    )
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    return conn


def generate_sql(question: str) -> str:
    llm = ChatOllama(model=GENERATION_MODEL, temperature=0)
    chain = SQL_GENERATION_PROMPT | llm | StrOutputParser()
    raw_sql = chain.invoke({"schema": SCHEMA_DESCRIPTION, "question": question})
    return raw_sql.strip().strip("`").removeprefix("sql\n").strip()


def execute_query(sql: str):
    conn = get_readonly_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        return columns, rows
    finally:
        conn.close()


def format_answer(question: str, sql: str, columns: list, rows: list) -> str:
    result_str = f"Colonnes : {columns}\nLignes : {rows[:50]}"
    llm = ChatOllama(model=GENERATION_MODEL, temperature=0)
    chain = ANSWER_PROMPT | llm | StrOutputParser()
    return chain.invoke({"question": question, "sql": sql, "result": result_str})


def answer_question(question: str) -> dict:
    raw_sql = generate_sql(question)
    print(f"[SQL généré]    {raw_sql}")

    try:
        safe_sql = validate_and_secure_sql(raw_sql)
    except UnsafeQueryError as e:
        return {"blocked": True, "reason": str(e), "raw_sql": raw_sql}

    print(f"[SQL sécurisé]  {safe_sql}")
    columns, rows = execute_query(safe_sql)
    answer = format_answer(question, safe_sql, columns, rows)

    return {"blocked": False, "sql": safe_sql, "columns": columns, "rows": rows, "answer": answer}


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "Combien de transactions frauduleuses ont été détectées au total ?"
    print(f"Question : {question}\n")

    result = answer_question(question)
    if result["blocked"]:
        print(f"\n🚫 Requête bloquée par les garde-fous : {result['reason']}")
    else:
        print(f"\n{result['answer']}")