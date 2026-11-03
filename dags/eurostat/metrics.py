"""Read-only, SQL-calculated evidence for economic reports and charts."""

import hashlib
import json
from datetime import timezone
from decimal import Decimal

from psycopg2 import sql

from eurostat.config import DATASETS
from eurostat.database import get_connection

COUNTRIES = {
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "PL": "Poland",
    "EU27_2020": "EU aggregate",
}


def direction(change):
    if change is None:
        return "unavailable"
    value = Decimal(change)
    return "increased" if value > 0 else "decreased" if value < 0 else "unchanged"


def collect_evidence(connection_factory=None):
    """Use one consistent snapshot; never accept SQL from the model."""
    connection = (connection_factory or get_connection)()
    facts, history, ingestion_times = [], {}, []
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '10s'")
                for indicator, config in DATASETS.items():
                    conditions = [sql.SQL("unit = %s"), sql.SQL("geo = ANY(%s)")]
                    parameters = [config["params"]["unit"], config["geos"]]
                    if indicator == "gdp":
                        conditions.append(sql.SQL("na_item = %s"))
                        parameters.append(config["params"]["na_item"])
                    change = (
                        sql.SQL("round(100 * (value / nullif(previous_value, 0) - 1), 2)")
                        if indicator == "gdp"
                        else sql.SQL("round(value - previous_value, 2)")
                    )
                    scale = 1000 if indicator == "gdp" else 1
                    cursor.execute(
                        sql.SQL("""
                        WITH observations AS (
                            SELECT geo, time_period::integer AS year, value,
                                   source_status, source_updated, snapshot_ts,
                                   lag(value) OVER (PARTITION BY geo ORDER BY time_period::integer) AS previous_value,
                                   lag(time_period::integer) OVER (PARTITION BY geo ORDER BY time_period::integer) AS previous_year
                            FROM {} WHERE {}
                        )
                        SELECT geo, year, round(value / %s, 2), source_status, source_updated,
                               CASE WHEN year = previous_year + 1 THEN {} END,
                               previous_year, snapshot_ts, value::text
                        FROM observations ORDER BY geo, year
                    """).format(
                            sql.Identifier(config["table"]),
                            sql.SQL(" AND ").join(conditions),
                            change,
                        ),
                        parameters + [scale],
                    )
                    rows = cursor.fetchall()
                    if {row[0] for row in rows} != set(config["geos"]):
                        raise ValueError(
                            f"Report needs stored observations for every configured {indicator} geography"
                        )
                    series = []
                    latest = {}
                    for (
                        geo,
                        year,
                        value,
                        flag,
                        updated,
                        change_value,
                        previous_year,
                        ingested,
                        raw,
                    ) in rows:
                        entry = {
                            "country_code": geo,
                            "country": COUNTRIES.get(geo, geo),
                            "year": year,
                            "value": str(value),
                            "source_status": flag,
                            "source_updated": updated,
                            "change": str(change_value) if change_value is not None else None,
                            "previous_year": previous_year,
                            "raw_value": raw,
                        }
                        series.append(entry)
                        latest[geo] = entry
                        if ingested:
                            ingestion_times.append(
                                ingested.replace(tzinfo=timezone.utc).isoformat()
                            )
                    history[indicator] = series
                    for geo in sorted(latest):
                        row = latest[geo]
                        facts.append(
                            {
                                **row,
                                "id": f"{indicator}_{geo}_{row['year']}",
                                "indicator": indicator,
                                "unit": "billion EUR, current prices"
                                if indicator == "gdp"
                                else "percent of population aged 15-64, both sexes",
                                "change_unit": "nominal percent"
                                if indicator == "gdp"
                                else "percentage points",
                                "direction": direction(row["change"]),
                                "source_url": f"https://ec.europa.eu/eurostat/databrowser/view/{config['code']}/default/table?lang=en",
                            }
                        )
    finally:
        connection.close()
    fingerprint = hashlib.sha256(json.dumps(history, sort_keys=True).encode()).hexdigest()
    return {
        "facts": facts,
        "history": history,
        "fingerprint": fingerprint,
        "latest_ingestion_utc": max(ingestion_times) if ingestion_times else None,
    }
