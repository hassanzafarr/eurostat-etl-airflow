# Developer guide

The tested runtime uses Python 3.11, Apache Airflow 2.10.2, PostgreSQL 15, and Docker Compose. See the [README](../README.md) for initial setup and the [design notes](DESIGN.md) for tradeoffs and deployment boundaries.

## Workflow and storage

The `eurostat_economic_indicators` DAG runs five tasks:

```text
create_tables
    +-- etl_gdp ---------+
    +-- etl_employment --+--> preview_data --> generate_insights
```

Each dataset task extracts, transforms, validates, and loads its own series. The branches can run independently; the preview waits for both. The report task renders charts and optionally adds validated Claude commentary. Large API responses and DataFrames stay out of Airflow XCom.

Airflow metadata uses the `airflow` database; observations use the separate `eurostat` database on the same PostgreSQL service. The connection is supplied as `AIRFLOW_CONN_EUROSTAT_POSTGRES`; environment-supplied connections do not appear in Airflow's Connections table.

The separate `ask_eurostat` DAG answers manually submitted questions against stored observations. It has no schedule and does not rerun ingestion. See [question planning and limits](ASK_EUROSTAT.md) and [AI validation and caching](AI_INTEGRATION.md).

## Loading and validation

- Every run fetches the configured history from 2015 onward and applies upserts, including revisions to older years.
- Validation checks geographies, annual periods, units, fixed employment filters, required fields, finite nonnegative values, employment rates no higher than 100%, and unique observation keys.
- Dataset tasks allow two retries, five minutes apart, with a ten-minute execution timeout per attempt. Empty datasets and HTTP errors fail visibly.
- All insert batches for one dataset share a transaction. A failure rolls back that dataset's load. GDP and employment commit independently.
- Records missing from later responses are retained. Tables store latest known values, without a complete revision history.
- Source flags, source update metadata, and ingestion timestamps are preserved.
- `max_active_runs=1` prevents overlapping collection runs. The preview reads a consistent, read-only database snapshot.

Changing units, age groups, sex, or indicators requires reviewing the table contract and migrating or separating the series. See the [data dictionary](DATA_DICTIONARY.md).

## Query and export

Open a SQL shell using the default demo credentials:

```bash
docker compose exec postgres psql -U airflow -d eurostat
```

```sql
SELECT geo, time_period, value, unit, source_status
FROM eurostat_gdp
WHERE geo = 'DE'
ORDER BY time_period::integer;
```

Type `\q` to exit. To use a desktop database client, connect to `localhost:5432`, database `eurostat`, schema `public`, with user/password `airflow` / `airflow`, unless configured differently.

Run the analysis queries and export the current database observations:

```bash
docker compose exec -T postgres psql -U airflow -d eurostat -f /analysis/analysis.sql
docker compose exec -T airflow-scheduler python scripts/export_data.py
```

Regenerate documentation charts from the exported CSV files in a host Python 3.11 environment:

```bash
python -m pip install -r requirements-analysis.txt
python scripts/plot_analysis.py
```

## Run checks

With the services running, execute the complete suite and code checks:

```bash
docker compose exec -T -e TEST_DATABASE_URL=postgresql://airflow:airflow@postgres:5432/eurostat airflow-scheduler python -m pytest -q tests
docker compose exec -T airflow-scheduler python -m ruff check dags tests scripts
docker compose exec -T airflow-scheduler python -m ruff format --check dags tests scripts
```

Use your configured password in `TEST_DATABASE_URL` if it differs. Database tests create isolated temporary schemas and clean them up; they do not write to the analytics tables in `public`.

Tests cover synthetic API fixtures, parser and data contracts, HTTP failures, real PostgreSQL behavior, Airflow dependencies, and AI output validation, including 22 golden evaluations. Documentation charts use actual exported observations rather than synthetic fixtures.

[GitHub Actions](../.github/workflows/ci.yml) builds the image, checks Compose configuration and formatting, and runs the suite against a fresh PostgreSQL database. Live Eurostat access is an opt-in manual check. The Anthropic key is not configured in CI.

For a live workflow check that restores the original pause state:

```bash
docker compose exec -T airflow-scheduler python scripts/smoke_test.py
```

See [verification results](VERIFICATION.md) and the [fresh-volume procedure](OPERATIONS.md) to reproduce the captured evidence in an isolated Compose project.

## Code map

| Location | Purpose |
|---|---|
| `dags/eurostat_etl_dag.py` | Collection and reporting workflow |
| `dags/ask_eurostat_dag.py` | Manual question form and answer task |
| `dags/eurostat/config.py` | Dataset filters |
| `dags/eurostat/etl.py` | API extraction, JSON-stat parsing, validation |
| `dags/eurostat/database.py`, `schema.sql` | Transactional storage and shared schema |
| `dags/eurostat/preview.py` | Read-only task-log data preview |
| `dags/eurostat/metrics.py` | SQL-calculated report evidence |
| `dags/eurostat/claude.py` | Provider calls and report output checks |
| `dags/eurostat/insights.py`, `report.py` | Cached commentary, report rendering, plots |
| `dags/eurostat/questions.py` | Bounded question planning, answers, and caching |
| `sql/analysis.sql` | Analysis queries |
| `scripts/` | Smoke checks, exports, chart generation, screenshots |
| `tests/` | Offline, database, DAG, and AI checks |

Ports bind to localhost. `.env`, execution logs, caches, and generated local artifacts are ignored by Git. Runtime dependencies are pinned against the Airflow image's constraints. Review and upgrade the runtime before external deployment; this setup is intended as a local demonstration.
