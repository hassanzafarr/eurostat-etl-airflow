"""Daily Eurostat ingestion with independent dataset tasks and a data preview."""

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator
from eurostat.config import DATASETS
from eurostat.database import create_tables, load_to_postgres
from eurostat.etl import extract_eurostat, parse_jsonstat_to_df, validate_data
from eurostat.preview import preview_data


def run_etl_for_dataset(dataset_key: str):
    raw = extract_eurostat(dataset_key)
    frame = parse_jsonstat_to_df(raw, dataset_key)
    validate_data(frame, dataset_key)
    load_to_postgres(frame, DATASETS[dataset_key]["table"])


with DAG(
    dag_id="eurostat_economic_indicators",
    description="Eurostat GDP and employment: validated API data to PostgreSQL",
    default_args={
        "owner": "Hassan Zafar",
        "depends_on_past": False,
        "email_on_failure": False,
        "email_on_retry": False,
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=10),
    },
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["etl", "eurostat", "postgres", "portfolio"],
) as dag:
    init = PythonOperator(
        task_id="create_tables", python_callable=create_tables, do_xcom_push=False
    )
    preview = PythonOperator(
        task_id="preview_data", python_callable=preview_data, do_xcom_push=False
    )
    for key in DATASETS:
        task = PythonOperator(
            task_id=f"etl_{key}",
            python_callable=run_etl_for_dataset,
            op_kwargs={"dataset_key": key},
            do_xcom_push=False,
        )
        init >> task >> preview
