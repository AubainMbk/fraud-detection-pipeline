"""
Interface Streamlit pour FraudLens -- démo visuelle du RAG + text-to-SQL + orchestrateur.
Lancer avec : streamlit run scripts/fraudlens/streamlit_app.py
"""
import streamlit as st
from orchestrator import route_question

st.set_page_config(page_title="FraudLens", page_icon="🔍", layout="centered")

st.title("🔍 FraudLens")
st.caption(
    "Assistant fraude bancaire -- documentation de compliance et données de "
    "transactions, en langage naturel. 100% local (Ollama + PostgreSQL/pgvector)."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("category"):
            st.caption(f"Routage : {message['category']}")
        if message.get("detail"):
            with st.expander(message.get("detail_label", "Détails")):
                st.code(message["detail"])

question = st.chat_input("Posez votre question...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyse et génération de la réponse (~10-30s en local)..."):
            result = route_question(question)
        st.markdown(result["answer"])
        st.caption(f"Routage : {result['category']}")
        if result.get("detail"):
            with st.expander(result.get("detail_label", "Détails")):
                st.code(result["detail"])

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "category": result["category"],
        "detail": result.get("detail"),
        "detail_label": result.get("detail_label"),
    })

with st.sidebar:
    st.header("À propos")
    st.markdown(
        "FraudLens route chaque question vers :\n"
        "- **RAG documentaire** (procédures de compliance)\n"
        "- **Text-to-SQL** (données de transactions), sécurisé par 3 couches "
        "indépendantes : rôle Postgres en lecture seule, validation de la "
        "requête (sqlglot), timeout d'exécution.\n\n"
        "Testé avec succès contre une tentative d'injection de prompt."
    )
    if st.button("Réinitialiser la conversation"):
        st.session_state.messages = []
        st.rerun()
