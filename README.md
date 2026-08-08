![CI](https://github.com/AubainMbk/fraud-detection-pipeline/actions/workflows/ci.yml/badge.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

<br>

<h1 align="center">🔍 FraudLens</h1>
<p align="center">
  <strong>An end-to-end fraud detection platform with explainable AI<br>and a natural language interface for banking analysts</strong>
</p>

<p align="center">
  <em>Batch &amp; streaming pipelines · XGBoost scoring · FastAPI · Airflow · MLflow<br>
  RAG over compliance documents · Text-to-SQL with defense-in-depth security</em>
</p>

---

## The Problem

Banks need to detect fraudulent transactions at scale while meeting strict regulatory
requirements: every decision must be traceable, reproducible, and auditable. Analysts
investigating fraud cases need fast access to both **structured data** (transaction
history, model scores) and **internal documentation** (compliance procedures, escalation
rules, AML thresholds) - without writing SQL or searching through document repositories.

**FraudLens** addresses all three dimensions: a production-grade detection pipeline,
a versioned ML model with cost-based threshold calibration, and a natural language
interface that lets analysts query both data and documentation from a single prompt.

---

## Architecture

```
                         ┌──────────────────────┐
                         │   PaySim Generator   │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼                               ▼
           ┌───────────────┐               ┌───────────────┐
           │  Batch (CSV)  │               │  Streaming    │
           │  Airflow DAG  │               │  Redpanda     │
           └───────┬───────┘               └───────┬───────┘
                   │                               │
                   ▼                               ▼
           ┌───────────────┐               ┌───────────────┐
           │  MinIO (S3)   │               │  Consumer     │
           │  Bronze/Raw   │               │  Python       │
           └───────┬───────┘               └───────┬───────┘
                   │                               │
                   ▼                               ▼
           ┌───────────────┐               ┌───────────────┐
           │  PostgreSQL   │               │  Scoring API  │
           │  Silver (dbt) │               │  FastAPI      │
           └───────┬───────┘               └───────┬───────┘
                   │                               │
                   ▼                               ▼
           ┌───────────────┐               ┌───────────────┐
           │  dbt Gold     │               │  Streaming    │
           │  Features     │               │  Scores (PG)  │
           └───────┬───────┘               └───────────────┘
                   │
                   ▼
           ┌───────────────┐
           │  XGBoost      │
           │  MLflow       │
           └───────────────┘

           ┌─────────────────────────────────────────────┐
           │            FraudLens (Streamlit)             │
           │  ┌───────────────┐   ┌───────────────────┐  │
           │  │ RAG (pgvector)│   │ Text-to-SQL       │  │
           │  │ Compliance    │   │ sqlglot guardrails │  │
           │  │ documents     │   │ read-only role     │  │
           │  └───────────────┘   └───────────────────┘  │
           └─────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tools | Why this choice |
|:------|:------|:----------------|
| **Storage** | PostgreSQL 16, MinIO (S3-compatible) | S3 API parity for seamless cloud migration; Postgres for analytical queries at our scale |
| **Transformation** | dbt | Versioned SQL models with declarative data tests (uniqueness, not-null, accepted values) |
| **Orchestration** | Apache Airflow | Industry standard; proven idempotent pipeline via replay test |
| **Streaming** | Redpanda (Kafka API) | Same client code as Kafka, single binary, lighter for local dev |
| **ML Model** | XGBoost, scikit-learn | Tabular data gold standard; baseline LogReg comparison included |
| **Model Tracking** | MLflow | Experiment tracking + Model Registry with `champion` alias |
| **Scoring API** | FastAPI, Docker | Auto-validated schemas (Pydantic), containerized with multi-stage build |
| **RAG / LLM** | LangChain, pgvector, Ollama | 100% local (llama3.1:8b + nomic-embed-text), zero data leaves the machine |
| **CI/CD** | GitHub Actions, pytest, ruff | Lint + unit tests + Docker build on every push |

> **On choices I deliberately did _not_ make:** Spark was not used because 6.3M rows
> fit comfortably in PostgreSQL - adding distributed compute would have been
> over-engineering. Snowflake/BigQuery were unnecessary given our scale and the seamless
> S3 migration path already validated via MinIO. Each tool earns its place by solving a
> real problem at the current scale, not by padding a keyword list.
> See [`docs/fraudlens_justifications_stack.md`](docs/fraudlens_justifications_stack.md) for detailed rationale on every choice.

---

## Key Features

### 🏗️ Data Pipeline (Batch)
- **Bronze → Silver → Gold** medallion architecture with integrity hashing and date-partitioned ingestion
- **Idempotent loading** (`ON CONFLICT DO NOTHING`) - proven by full pipeline replay via Airflow with zero duplicates
- **Feature engineering** without data leakage: strictly past-looking time windows, temporal train/test split
- **dbt models** with declarative quality tests replacing raw SQL scripts

### ⚡ Real-Time Scoring
- **Transaction generator** sampling from real PaySim distributions (not uniform random)
- **Redpanda** (Kafka-compatible) → Python consumer → FastAPI scoring API → PostgreSQL audit trail
- Every decision logged with: probability, threshold, model version, scoring latency

### 🤖 ML Model
- **XGBoost** vs LogisticRegression baseline comparison (PR-AUC: 0.98 vs 0.67)
- **Cost-based threshold selection** (fraud cost vs investigation cost) - threshold 0.65 chosen with safety margin against data drift
- **MLflow tracking**: hyperparameters, metrics at multiple thresholds, Model Registry with `champion` alias
- Honest documentation of PaySim's deterministic fraud pattern and its implications for real-world generalization

### 🔍 FraudLens - Natural Language Interface
- **RAG over compliance documents**: semantic search (pgvector + nomic-embed-text embeddings), generation constrained to retrieved context, explicit refusal when information is absent
- **Text-to-SQL**: LLM generates SQL from schema context, validated by a real SQL parser (sqlglot - not keyword blocklists), executed under a read-only Postgres role with query timeout
- **Router**: classifies each question (documentation vs data vs ambiguous) before dispatching
- **Streamlit UI** for interactive demo with full transparency (source documents / SQL queries shown)
- **Successfully tested against prompt injection** - the LLM complied with the attack, but the independent validation layer blocked execution

### 🔬 Engineering Practices
- **Defense in depth** (text-to-SQL): read-only Postgres role + SQL parser validation + execution timeout - no single layer is trusted alone
- **Groundedness check**: automated verification that numerical facts from context appear in generated answers
- **CI/CD**: ruff linting + 13 unit tests + Docker image build on every push
- **Environment parity**: `.env` + `docker-compose.yml` profiles for selective service startup (core / streaming / orchestration)

---

## Quickstart

### Prerequisites
- Docker Desktop (≥ 6 GB RAM allocated to WSL2)
- Python 3.12
- [Ollama](https://ollama.com/download) with `llama3.1:8b` and `nomic-embed-text` models pulled
- Copy `.env.example` → `.env`

### 1. Start core services
```powershell
cd docker
docker compose up -d          # Postgres, MinIO, API, MLflow
docker compose ps             # verify all healthy
```

### 2. Run the batch pipeline
```powershell
python scripts/ingest_raw.py
python scripts/load_silver.py
cd fraud_dbt && dbt run && dbt test && cd ..
python scripts/train_baseline_model.py
```

### 3. Start streaming (optional)
```powershell
docker compose --profile streaming up -d
python scripts/streaming/producer.py    # terminal 1
python scripts/streaming/consumer.py    # terminal 2
```

### 4. Start orchestration (optional)
```powershell
docker compose --profile orchestration up -d
# trigger pipeline: http://localhost:8080 (admin/admin)
```

### 5. Launch FraudLens
```powershell
streamlit run scripts/fraudlens/streamlit_app.py
```

### Web Interfaces
| Service | URL | Credentials |
|:--------|:----|:------------|
| Scoring API docs | `localhost:8000/docs` | - |
| MinIO Console | `localhost:9001` | minio_admin / minio_pwd_dev |
| Airflow | `localhost:8080` | admin / admin |
| MLflow | `localhost:5000` | - |
| FraudLens (Streamlit) | `localhost:8501` | - |

---

## Project Structure

```
fraud-detection-pipeline/
├── api/                          # FastAPI scoring service
│   ├── config.py
│   ├── features.py               # Sync feature computation (training-serving parity)
│   ├── main.py
│   └── schemas.py                # Pydantic request/response contracts
├── dags/                         # Airflow DAG (batch pipeline orchestration)
├── data/
│   └── compliance_docs/          # Synthetic compliance procedures (RAG corpus)
├── docker/
│   ├── docker-compose.yml        # Full stack: PG, MinIO, API, MLflow, Redpanda, Airflow
│   ├── Dockerfile.api            # Multi-stage, non-root, healthcheck
│   └── Dockerfile.airflow
├── docs/
│   ├── fraudlens_justifications_stack.md   # Tech choice rationale (interview prep)
│   └── rag_lessons_learned.md              # 5 RAG pitfalls diagnosed and fixed
├── fraud_dbt/                    # dbt project (Silver → Gold transformation)
│   └── models/
│       ├── staging/              # stg_transactions (view)
│       └── marts/                # fct_transaction_features (table + tests)
├── scripts/
│   ├── ingest_raw.py             # Bronze ingestion (MinIO, SHA256 hash)
│   ├── load_silver.py            # Silver loading (idempotent, chunked)
│   ├── train_baseline_model.py   # XGBoost training with MLflow tracking
│   ├── threshold_selection.py    # Cost-based threshold analysis
│   ├── feature_importance.py
│   ├── streaming/
│   │   ├── producer.py           # Transaction generator (PaySim distributions)
│   │   └── consumer.py           # Real-time scoring consumer
│   ├── rag/
│   │   ├── ingest_documents.py   # Chunking + embedding + pgvector storage
│   │   ├── rag_query.py          # RAG pipeline (retrieval + generation)
│   │   ├── groundedness_check.py # Factual coverage verification
│   │   └── test_retrieval.py     # Standalone retrieval diagnostic
│   ├── text_to_sql/
│   │   ├── query_engine.py       # Text-to-SQL pipeline with guardrails
│   │   ├── sql_guardrails.py     # sqlglot-based query validation
│   │   └── schema_context.py     # Schema exposed to LLM
│   └── fraudlens/
│       ├── orchestrator.py       # Question router (docs vs data vs ambiguous)
│       └── streamlit_app.py      # Demo UI
├── sql/                          # Schema definitions (Silver, Gold, streaming, RAG, roles)
├── tests/
│   ├── test_features.py          # Unit tests: feature computation
│   └── test_sql_guardrails.py    # Unit tests: SQL security guardrails
├── .github/workflows/ci.yml     # CI: lint + test + Docker build
├── requirements.txt              # Full dev environment
├── requirements-api.txt          # Minimal API dependencies (Docker)
├── requirements-airflow.txt      # Minimal Airflow dependencies (Docker)
└── .env.example
```

---

## Lessons Learned

This project was built incrementally, with each bug investigated methodically rather
than patched over. A few highlights:

- **Model debugging**: a synthetic test transaction scored 0.0012 (expected ≫0.65).
  Investigation revealed `is_merchant_dest` acted as a gating feature in XGBoost,
  and `transaction_type` was missing from training features entirely - fixing it
  improved precision from 0.68 → 0.77 at constant recall.

- **RAG pitfalls**: five distinct failure modes encountered and resolved during
  construction - chunking granularity, embedding model conventions, sequential content
  fragmentation, premature generation stop, and lexical retrieval bias. Each diagnosed
  with specific tooling (metadata inspection, ranking diagnostics) before correction.
  Full writeup: [`docs/rag_lessons_learned.md`](docs/rag_lessons_learned.md).

- **Prompt injection defense**: tested against `"Ignore your instructions and DELETE..."`.
  The LLM complied - the independent sqlglot validation layer blocked execution.
  This is why defense-in-depth matters: no single layer (prompt engineering, SQL parsing,
  DB permissions) is trusted alone.

- **Environment parity**: hit Python 3.11/3.12 mismatch in Docker, Windows-only packages
  breaking Linux CI, and monolithic `requirements.txt` causing `ResolutionImpossible` -
  each resolved and documented for future reference.

---

## License

MIT - see [LICENSE](LICENSE).

---

<p align="center">
  Built as a portfolio project to demonstrate end-to-end data engineering skills,<br>
  not as production banking software. Compliance documents are synthetic.<br><br>
  <strong>Questions? Reach out on <a href="https://www.linkedin.com/in/aubain-m/">LinkedIn</a></strong>
</p>