"""Transactional PostgreSQL storage; connections are injected for testing."""

import logging
from pathlib import Path

import pandas as pd
from psycopg2 import sql
from psycopg2.extras import execute_values

from eurostat.config import DATASETS, POSTGRES_CONN_ID

logger = logging.getLogger(__name__)


def get_connection():
    # Lazy import lets parser and database tests run without an Airflow installation.
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    return PostgresHook(postgres_conn_id=POSTGRES_CONN_ID).get_conn()


def _table_keys(table: str) -> list[str]:
    if table not in {config["table"] for config in DATASETS.values()}:
        raise ValueError(f"Unknown target table: {table}")
    return (
        ["geo", "time_period", "na_item"]
        if table == DATASETS["gdp"]["table"]
        else ["geo", "time_period"]
    )


def load_to_postgres(df: pd.DataFrame, table: str, connection_factory=None):
    """Atomically upsert observations, preserving historical rows absent from the API."""
    keys = _table_keys(table)
    if df.empty:
        raise ValueError(f"Refusing an empty load into {table}")
    if df[keys].isna().any().any() or df.duplicated(keys).any():
        raise ValueError(f"Missing or duplicate observation keys for {table}")
    if (
        not pd.to_numeric(df["value"], errors="coerce")
        .map(lambda value: pd.notna(value) and float("-inf") < value < float("inf"))
        .all()
    ):
        raise ValueError("Non-finite values cannot be loaded")
    columns = [
        "geo",
        "time_period",
        "value",
        "unit",
        "na_item",
        "dataset",
        "snapshot_ts",
        "source_status",
        "source_updated",
    ]
    records = df.reindex(columns=columns).astype(object)
    records = records.where(pd.notna(records), None)
    updates = [column for column in columns if column not in keys]
    statement = sql.SQL("INSERT INTO {} ({}) VALUES %s ON CONFLICT ({}) DO UPDATE SET {}").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(map(sql.Identifier, keys)),
        sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
            for column in updates
        ),
    )
    connection = (connection_factory or get_connection)()
    try:
        with connection:
            with connection.cursor() as cursor:
                execute_values(
                    cursor,
                    statement.as_string(cursor),
                    list(records.itertuples(index=False, name=None)),
                )
    finally:
        connection.close()
    logger.info("Loaded %s rows into %s", len(df), table)


def create_tables(connection_factory=None):
    """Apply the shared idempotent schema to the selected database."""
    connection = (connection_factory or get_connection)()
    schema_path = Path(__file__).with_name("schema.sql")
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(schema_path.read_text(encoding="utf-8"))
    finally:
        connection.close()
    logger.info("Eurostat tables ready")
