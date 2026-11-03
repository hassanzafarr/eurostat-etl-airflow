"""Real PostgreSQL tests isolated in a unique schema per test."""

import json
from pathlib import Path

import pandas as pd
import psycopg2
import pytest
from eurostat.database import create_tables, load_to_postgres
from eurostat.etl import parse_jsonstat_to_df

pytestmark = pytest.mark.integration


def records(factory, query):
    connection = factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    finally:
        connection.close()


def frame_for(key):
    payload = json.loads((Path(__file__).parent / "fixtures" / f"{key}.json").read_text())
    return parse_jsonstat_to_df(payload, key)


@pytest.mark.parametrize("key", ["gdp", "employment"])
def test_reruns_update_values_without_duplicates_or_history_loss(database, key):
    frame = frame_for(key)
    table = "eurostat_" + key
    load_to_postgres(frame, table, database)
    load_to_postgres(frame, table, database)
    assert records(database, f"SELECT count(*) FROM {table}")[0][0] == 14
    revision = frame.iloc[[0]].copy()
    revision.loc[revision.index[0], "value"] = 99
    load_to_postgres(revision, table, database)
    assert records(database, f"SELECT count(*) FROM {table}")[0][0] == 14
    assert (
        records(database, f"SELECT value FROM {table} WHERE geo='DE' AND time_period='2023'")[0][0]
        == 99
    )
    assert (
        records(
            database, f"SELECT source_status FROM {table} WHERE geo='PL' AND time_period='2024'"
        )[0][0]
        == "e"
    )


def test_second_insert_page_failure_rolls_back_first_page(database):
    connection = database()
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE eurostat_gdp ADD CONSTRAINT test_value_limit CHECK (value < 2000)"
            )
    connection.close()
    seed = frame_for("gdp").iloc[[0]]
    frame = pd.concat([seed] * 101, ignore_index=True)
    frame["time_period"] = [str(1900 + i) for i in range(101)]
    frame.loc[100, "value"] = 3000
    with pytest.raises(psycopg2.errors.CheckViolation):
        load_to_postgres(frame, "eurostat_gdp", database)
    assert records(database, "SELECT count(*) FROM eurostat_gdp")[0][0] == 0


def test_schema_can_be_applied_repeatedly(database):
    create_tables(database)
    create_tables(database)
    load_to_postgres(frame_for("employment"), "eurostat_employment", database)
    assert records(database, "SELECT count(*) FROM eurostat_employment")[0][0] == 14
