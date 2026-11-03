"""Read-only previews for the Airflow task log."""

import logging

import pandas as pd
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2 import sql

from eurostat.config import DATASETS, POSTGRES_CONN_ID

logger = logging.getLogger(__name__)


def preview_data():
    """Print a bounded, read-only preview of the stored data in Airflow logs."""
    countries = {
        "DE": "Germany",
        "FR": "France",
        "IT": "Italy",
        "ES": "Spain",
        "NL": "Netherlands",
        "PL": "Poland",
        "EU27_2020": "European Union",
    }
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    connection = hook.get_conn()
    try:
        with connection:
            with connection.cursor() as cursor:
                # One consistent, read-only snapshot for all preview queries.
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                logger.info(
                    "\n========== EUROSTAT DATA PREVIEW ==========\nSource: PostgreSQL eurostat database"
                )
                for key, config in DATASETS.items():
                    table = sql.Identifier(config["table"])
                    conditions = [sql.SQL("unit = %s"), sql.SQL("geo = ANY(%s)")]
                    parameters = [config["params"]["unit"], config["geos"]]
                    if "na_item" in config["params"]:
                        conditions.append(sql.SQL("na_item = %s"))
                        parameters.append(config["params"]["na_item"])
                    where = sql.SQL(" AND ").join(conditions)
                    cursor.execute(
                        sql.SQL("""
                        SELECT count(*), min(time_period::integer), max(time_period::integer)
                        FROM {} WHERE {}
                    """).format(table, where),
                        parameters,
                    )
                    count, first_year, last_year = cursor.fetchone()
                    if not count:
                        raise ValueError(f"No stored data available to preview for {key}")
                    cursor.execute(
                        sql.SQL("""
                        SELECT DISTINCT ON (geo) geo, time_period, value
                        FROM {} WHERE {}
                        ORDER BY geo, time_period::integer DESC
                        LIMIT %s
                    """).format(table, where),
                        parameters + [len(config["geos"])],
                    )
                    frame = pd.DataFrame(cursor.fetchall(), columns=["Country", "Year", "Value"])
                    frame["Country"] = frame["Country"].map(lambda geo: countries.get(geo, geo))
                    if key == "gdp":
                        title = (
                            "GDP - latest available year per country (billion EUR, current prices)"
                        )
                        frame["Value"] = frame["Value"].map(lambda value: f"{value / 1000:,.2f}")
                        frame = frame.rename(columns={"Value": "GDP (billion EUR)"})
                    else:
                        title = "Employment - latest available year per country (ages 15-64, both sexes)"
                        frame["Value"] = frame["Value"].map(lambda value: f"{value:.1f}%")
                        frame = frame.rename(columns={"Value": "Employment rate"})
                    logger.info(
                        "\n%s\nStored observations: %s | Coverage: %s-%s\n%s",
                        title,
                        count,
                        first_year,
                        last_year,
                        frame.to_string(index=False),
                    )

                cursor.execute("""
                    WITH history AS (
                        SELECT time_period::integer AS year, value,
                               lag(value) OVER (ORDER BY time_period::integer) AS previous_value,
                               lag(time_period::integer) OVER (ORDER BY time_period::integer) AS previous_year
                        FROM eurostat_gdp
                        WHERE geo = 'DE' AND unit = 'CP_MEUR' AND na_item = 'B1GQ'
                    )
                    SELECT year, round(value / 1000, 2),
                           CASE WHEN year = previous_year + 1 THEN
                               round(100 * (value / nullif(previous_value, 0) - 1), 2)
                           END
                    FROM history ORDER BY year DESC LIMIT 5
                """)
                trend = pd.DataFrame(
                    cursor.fetchall(), columns=["Year", "GDP (billion EUR)", "Annual change (%)"]
                )
                logger.info(
                    "\nGermany GDP - latest five years\n%s\n"
                    "Annual change uses current prices; it is not inflation-adjusted growth.\n"
                    "========== END DATA PREVIEW ==========",
                    trend.fillna("N/A").to_string(index=False),
                )
    finally:
        connection.close()
