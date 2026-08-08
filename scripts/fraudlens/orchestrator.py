"""
Orchestrateur FraudLens : reçoit une question en langage naturel, la classe
(documentation vs données), et route vers le bon sous-système (RAG ou text-to-SQL).
"""
import os
import sys

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

load_dotenv()

# Rendre les modules sœurs importables (scripts/rag, scripts/text_to_sql)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(PROJECT_ROOT, "scripts", "rag"))
sys.path.append(os.path.join(PROJECT_ROOT, "scripts", "text_to_sql"))

from query_engine import answer_question as sql_answer  # noqa: E402
from rag_query import answer_question as rag_answer  # noqa: E402

ROUTER_MODEL = "llama3.1:8b"

ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Tu classes une question posée par un analyste fraude dans une banque en "
        "une seule catégorie parmi : DOCUMENTATION ou DONNEES.\n"
        "- DOCUMENTATION : la question porte sur une procédure, une politique, un "
        "seuil réglementaire, une règle de conformité (ex: 'quelle est la procédure "
        "si...', 'quels sont les seuils AML').\n"
        "- DONNEES : la question porte sur des transactions, des scores, des chiffres "
        "précis à calculer depuis la base (ex: 'combien de...', 'quelles sont les "
        "transactions avec...', 'quel est le montant moyen de...').\n"
        "Réponds UNIQUEMENT avec le mot DOCUMENTATION ou le mot DONNEES, rien d'autre."
    ),
    ("human", "{question}"),
])


def classify_question(question: str) -> str:
    llm = ChatOllama(model=ROUTER_MODEL, temperature=0)
    chain = ROUTER_PROMPT | llm | StrOutputParser()
    raw = chain.invoke({"question": question}).strip().upper()

    if "DONNEES" in raw or "DONNÉES" in raw:
        return "DONNEES"
    if "DOCUMENTATION" in raw:
        return "DOCUMENTATION"
    return "INCERTAIN"


def route_question(question: str) -> dict:
    category = classify_question(question)

    if category == "DOCUMENTATION":
        answer, context = rag_answer(question)
        return {
            "category": category,
            "answer": answer,
            "detail": context,
            "detail_label": "Documents consultés",
        }

    if category == "DONNEES":
        result = sql_answer(question)
        if result["blocked"]:
            return {
                "category": category,
                "answer": f"🚫 Requête bloquée : {result['reason']}",
                "detail": None,
                "detail_label": None,
            }
        return {
            "category": category,
            "answer": result["answer"],
            "detail": result["sql"],
            "detail_label": "Requête SQL exécutée",
        }

    return {
        "category": "INCERTAIN",
        "answer": (
            "Je n'arrive pas à déterminer si votre question porte sur une procédure "
            "documentaire ou sur les données de transactions. Pouvez-vous reformuler ?"
        ),
        "detail": None,
        "detail_label": None,
    }


def main():
    print("=== FraudLens — Assistant fraude (RAG + text-to-SQL) ===")
    print("Tapez votre question, ou 'exit' pour quitter.\n")

    while True:
        question = input("Question > ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        result = route_question(question)
        print(f"\n[Routage : {result['category']}]")
        print(result["answer"])
        print()


if __name__ == "__main__":
    main()
