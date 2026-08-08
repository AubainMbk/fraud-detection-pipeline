CREATE SCHEMA IF NOT EXISTS rag;

-- 768 = dimension des embeddings produits par nomic-embed-text (le modèle Ollama qu'on utilise)
CREATE TABLE IF NOT EXISTS rag.compliance_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_name VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);