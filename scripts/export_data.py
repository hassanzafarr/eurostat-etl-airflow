"""Export bounded analytics snapshots from PostgreSQL for reproducible charts."""

import csv
from datetime import datetime, timezone
from pathlib import Path

from eurostat.database import get_connection


def main():
    destination = Path(__file__).resolve().parents[1] / "docs" / "data"
    destination.mkdir(parents=True, exist_ok=True)
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                for table in ("eurostat_gdp", "eurostat_employment"):
                    # Table names are fixed constants, never user input.
                    cursor.execute(
                        f"SELECT geo, time_period, value, unit, source_status, source_updated, snapshot_ts FROM {table} ORDER BY geo, time_period::integer"
                    )
                    with (destination / f"{table}.csv").open(
                        "w", newline="", encoding="utf-8"
                    ) as output:
                        writer = csv.writer(output)
                        writer.writerow([column.name for column in cursor.description])
                        writer.writerows(cursor.fetchall())
                    print("Exported", table, cursor.rowcount, "observations")
        (destination / "EXPORTED_AT.txt").write_text(
            datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8"
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
