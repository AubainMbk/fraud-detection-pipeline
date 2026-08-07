![CI](https://github.com/AubainMbk/fraud-detection-pipeline/actions/workflows/ci.yml/badge.svg)

# FraudLens - Plateforme de détection de fraude bancaire de bout en bout

Pipeline complet de détection de fraude : ingestion batch et streaming, feature engineering,
modèle de scoring versionné, API temps réel, orchestration, et une interface en langage
naturel (RAG) pour les équipes métier.

## Problématique

Comment détecter des transactions frauduleuses à grande échelle, garantir la traçabilité et
la reproductibilité des décisions (contrainte réglementaire bancaire), et permettre à un
analyste métier d'interroger le système sans écrire de SQL ?

## Stack technique

| Domaine | Outils |
|---|---|
| Stockage | PostgreSQL, MinIO (S3-compatible) |
| Transformation | dbt |
| Orchestration | Apache Airflow |
| Streaming | Redpanda (API Kafka) |
| Modèle ML | XGBoost, scikit-learn, MLflow (tracking + registry) |
| API | FastAPI, Docker |
| RAG / LLM | LangChain, pgvector, API Anthropic Claude |
| CI/CD | GitHub Actions, pytest, ruff |

## Architecture

Ingestion (Bronze) → Transformation dbt (Silver/Gold) → Feature engineering →
Modèle XGBoost (tracé MLflow) → API de scoring temps réel ← Producer/Consumer streaming (Redpanda)

L'ensemble batch est orchestré par Airflow ; l'ensemble est testé et construit
automatiquement via CI/CD à chaque push.

## Démarrage rapide

Prérequis : Docker Desktop, Python 3.12, un fichier `.env` (voir `.env.example`).

```powershell
# Services cœur (Postgres, MinIO, API, MLflow)
cd docker
docker compose up -d

# Optionnel : streaming
docker compose --profile streaming up -d

# Optionnel : orchestration Airflow
docker compose --profile orchestration up -d
```

Interfaces : API (`localhost:8000/docs`), MinIO (`localhost:9001`),
Airflow (`localhost:8080`), MLflow (`localhost:5000`).

## Ce qui a été implémenté

- [x] Ingestion batch tracée (hash d'intégrité, partitionnement par date) vers un data lake MinIO
- [x] Transformation Bronze → Silver idempotente (Postgres)
- [x] Feature engineering Gold sans fuite de données (fenêtres temporelles strictes), migré vers dbt avec tests de qualité déclaratifs
- [x] Modèle de scoring XGBoost, validé par split temporel, seuil calibré sur un arbitrage coût métier, tracé et versionné dans MLflow
- [x] API de scoring temps réel (FastAPI), conteneurisée
- [x] Pipeline streaming (Redpanda) : générateur de transactions → scoring en continu → traçabilité complète
- [x] Orchestration Airflow du pipeline batch, idempotence validée par rejeu
- [x] CI/CD (GitHub Actions) : lint, tests unitaires, build Docker à chaque push
- [ ] FraudLens : interface en langage naturel (RAG documentaire + text-to-SQL) - en cours

## Décisions techniques notables

Chaque choix (PostgreSQL plutôt que Spark à cette échelle, Redpanda plutôt que Kafka natif,
dbt par-dessus SQL brut, pgvector plutôt qu'une base vectorielle dédiée...) est documenté
et justifié à dessein - voir les commentaires dans le code et les messages de commit.