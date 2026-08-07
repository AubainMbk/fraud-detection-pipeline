"""
DAG Airflow : pipeline batch de détection de fraude.
Orchestre les trois étapes Bronze -> Silver -> Gold, dans un ordre strict.
Réutilise les scripts existants sans dupliquer leur logique.
"""
import os
from datetime import datetime, timedelta

import psycopg2
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

SCRIPTS_DIR = "/opt/airflow/scripts"
SQL_DIR = "/opt/airflow/sql"


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def run_sql_file(filename: str):
    """Exécute un fichier SQL complet contre fraud_db."""
    filepath = os.path.join(SQL_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()

    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fraud_batch_pipeline",
    description="Pipeline batch Bronze -> Silver -> Gold pour la détection de fraude",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["fraud", "batch"],
) as dag:

    ingest_raw = BashOperator(
        task_id="ingest_raw_to_minio",
        bash_command=f"cd /opt/airflow && python {SCRIPTS_DIR}/ingest_raw.py",
    )

    create_silver_schema = PythonOperator(
        task_id="create_silver_schema",
        python_callable=run_sql_file,
        op_kwargs={"filename": "01_create_silver_schema.sql"},
    )

    load_silver = BashOperator(
        task_id="load_bronze_to_silver",
        bash_command=f"cd /opt/airflow && python {SCRIPTS_DIR}/load_silver.py",
    )

    build_gold_features = PythonOperator(
        task_id="build_gold_features",
        python_callable=run_sql_file,
        op_kwargs={"filename": "02_create_gold_features.sql"},
    )

    ingest_raw >> create_silver_schema >> load_silver >> build_gold_features
