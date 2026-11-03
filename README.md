# Eurostat Economic Indicators ETL

[![Pipeline checks](https://github.com/hassanzafarr/eurostat-etl-airflow/actions/workflows/ci.yml/badge.svg)](https://github.com/hassanzafarr/eurostat-etl-airflow/actions/workflows/ci.yml)

A reproducible batch pipeline that turns Eurostat GDP and employment API responses into validated PostgreSQL tables. Apache Airflow schedules the work, retries failures, and generates an optional Claude Haiku economic report with SQL-backed evidence and plots.

**Python 3.11 | Apache Airflow 2.10.2 | PostgreSQL 15 | Docker Compose | Claude Haiku**

Built and maintained by Hassan Zafar. This project demonstrates API ingestion, multidimensional data parsing, data contracts, transactional SQL upserts, orchestration, and automated testing.

## See the result

![Successful five-task Airflow workflow](docs/images/airflow-workflow.png)

The verified snapshot contains **154 annual observations**: 77 GDP records and 77 employment records covering 2015-2025, for Germany, France, Italy, Spain, the Netherlands, Poland, and the EU aggregate. Counts describe the captured snapshot and can change when Eurostat publishes or revises data.

[Live-run verification](docs/verification.json) | [SQL analysis](sql/analysis.sql) | [Data dictionary](docs/DATA_DICTIONARY.md) | [Test workflow](.github/workflows/ci.yml)

## Architecture

```mermaid
flowchart LR
    E[Eurostat Statistics API] --> X[Python extraction]
    X --> V[JSON-stat parsing and validation]
    V --> P[(PostgreSQL: eurostat)]
    P --> L[Airflow data preview]
    P --> C[CSV snapshots and analysis charts]
    P --> M[SQL report metrics]
    M --> H[Optional Claude Haiku commentary]
    H --> R[Validated HTML report and plots]
    A[Airflow scheduler] -. coordinates .-> X
```

The DAG runs five tasks:

```text
create_tables
    +-- etl_gdp ---------+
    +-- etl_employment --+--> preview_data --> generate_insights
```

Each dataset task extracts, transforms, validates, and loads its own data. The two branches can run independently; the preview waits for both. The final task renders plots and optionally adds validated Haiku commentary. Large responses and DataFrames stay out of Airflow XCom. Airflow metadata uses the `airflow` database; analytics use the separate `eurostat` database on the same PostgreSQL service.

## Quick start

Prerequisites: Docker with Linux containers and Docker Compose. Allocate at least 4 GB of memory to Docker for a comfortable local demo. Windows users can use Docker Desktop with WSL2. No Eurostat API key is needed.

From the downloaded or cloned repository, copy the example configuration:

```powershell
# PowerShell
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

Then start the stack:

```bash
docker compose up --build -d
docker compose ps
```

The first build and database migration take a few minutes. `airflow-init` should exit with code 0; PostgreSQL, the scheduler, and webserver should become healthy.

1. Open [localhost:8080](http://localhost:8080).
2. Log in with `airflow` / `airflow` using the default demo configuration.
3. Open `eurostat_economic_indicators`, enable the DAG, and choose **Trigger DAG**.
4. Select the new run. All five tasks should become green.
5. Open **preview_data > Logs** and search for `EUROSTAT DATA PREVIEW`.

The schedule is **06:00 UTC daily** and new installations start paused. Enabling the DAG may also create the latest eligible scheduled run. Daily execution checks for updates to annual observations; it does not create daily economic measurements. Services must be running for the schedule to execute.

For a scripted end-to-end check that restores the original pause state:

```bash
docker compose exec -T airflow-scheduler python scripts/smoke_test.py
```

The PostgreSQL connection is supplied automatically as `AIRFLOW_CONN_EUROSTAT_POSTGRES`; environment-supplied connections do not appear in the Airflow Connections table.

## Claude Haiku reports and plots

Add `ANTHROPIC_API_KEY` to your private `.env` file and recreate the services. The default model is `claude-haiku-5-5`. Generate a report from stored observations:

```bash
docker compose up --build -d
docker compose exec -T airflow-scheduler python scripts/generate_report.py --require-ai
```

Open **artifacts/insights/latest.html** locally for commentary, evidence, sources, and GDP/employment plots. The folder also contains Markdown, JSON, and standalone PNG plots. In Airflow, open **generate_insights > Logs** for the text report.

[Integration and key setup](docs/AI_INTEGRATION.md) | [Real Haiku report example](docs/AI_REPORT_SAMPLE.md)

SQL computes figures and annual changes. Claude selects evidence-linked findings and writes qualitative wording; the application rejects numeric prose, unknown references, incorrect trend directions, and common unsupported claims. Successful commentary is cached when evidence, model, and prompt match. No key or unavailable API produces a clearly labelled report with verified data and plots. Use `--require-ai` to require live or cached commentary. The key stays local and is not configured in GitHub CI.

## Ask Claude directly in Airflow

Open [Ask Eurostat](http://localhost:8080/dags/ask_eurostat/trigger), enter **Your question**, and click **Trigger**. Select the new run, then **answer_question > Logs**, and search for **ASK EUROSTAT ANSWER**.

Examples: compare Germany and France employment in the latest year; show Germany GDP since 2015; ask how Germany GDP changed between 2015 and 2025. The separate `ask_eurostat` DAG reads existing data, accepts only bounded operations, and returns a cited answer with verified figures. It does not run on a schedule or modify source observations. Repeated questions reuse a cache when evidence and model/prompt settings match.

[Question form, examples and limits](docs/ASK_EUROSTAT.md)

## Reliability and loading strategy

- **Full historical extraction with upserts:** every run requests the configured series from 2015 onward, so revisions to older years are picked up. This is not incremental extraction.
- **Validation before loading:** enforce the configured countries, annual years, units, employment age/sex/indicator filters, non-null required fields, finite nonnegative values, employment rates at most 100%, and unique observation keys.
- **Failure visibility:** HTTP and validation errors fail the task. Airflow permits two retries after the initial attempt, five minutes apart, with a ten-minute execution timeout per attempt. Empty responses do not silently succeed.
- **Atomic database writes:** `INSERT ... ON CONFLICT DO UPDATE` updates observations in one transaction per dataset. Any insert failure rolls back the entire dataset load, including earlier insert batches.
- **History preservation:** observations absent from a later response are retained. The tables represent latest known values, not a versioned archive of every revision.
- **Provenance:** preserve Eurostat observation flags and source update metadata alongside the ingestion timestamp.
- **Bounded overlap:** `max_active_runs=1` prevents concurrent DAG runs; the preview uses a consistent read-only database snapshot.

These controls apply per dataset. GDP can commit successfully while employment fails; the preview is blocked until both succeed. [Design decisions and limitations](docs/DESIGN.md) explain the tradeoffs.

## Explore the data

Open a SQL shell:

```bash
docker compose exec postgres psql -U airflow -d eurostat
```

```sql
SELECT geo, time_period, value, unit, source_status
FROM eurostat_gdp
WHERE geo = 'DE'
ORDER BY time_period::integer;
```

Type `\q` to exit. Run the complete analysis file without installing PostgreSQL on your computer:

```bash
docker compose exec -T postgres psql -U airflow -d eurostat -f /analysis/analysis.sql
```

For a database client on your computer: host `localhost`, port `5432`, database `eurostat`, schema `public`, user/password `airflow` / `airflow` by default.

![Germany GDP at current prices](docs/images/germany-gdp.png)

![Employment trends across the selected countries](docs/images/employment-trends.png)

GDP is at current prices, so its annual change is nominal, not inflation-adjusted growth. Employment is the employed share of people aged 15-64, for both sexes. The EU aggregate overlaps the six countries and must not be added to their totals. Source flags can indicate provisional or estimated observations.

[Committed CSV snapshots](docs/data) let readers reproduce the figures without a running database. Refresh snapshots after a successful run:

Read the [snapshot analysis](docs/ANALYSIS.md) for the computed comparisons and interpretation limits. A [screenshot of the Airflow data preview](docs/images/airflow-preview.png) is also included.

```bash
docker compose exec -T airflow-scheduler python scripts/export_data.py
```

In a Python 3.11 environment, install `requirements-analysis.txt` and run:

```bash
python -m pip install -r requirements-analysis.txt
python scripts/plot_analysis.py
```

## Tests and continuous integration

The suite includes offline synthetic API fixtures, contract validation, HTTP failure handling, real PostgreSQL integration tests, DAG dependency checks, and 22 golden evaluations for AI output grounding. Fixtures are clearly marked as synthetic; the charts use real exported observations.

```bash
# All tests, including PostgreSQL and Airflow, inside the pinned runtime:
docker compose exec -T -e TEST_DATABASE_URL=postgresql://airflow:airflow@postgres:5432/eurostat airflow-scheduler python -m pytest -q tests

# Formatting and lint checks:
docker compose exec -T airflow-scheduler python -m ruff check dags tests scripts
docker compose exec -T airflow-scheduler python -m ruff format --check dags tests scripts
```

Use your configured password in `TEST_DATABASE_URL` if it differs. Database tests create unique temporary schemas and clean them up; they do not write to the analytics tables in `public`.

[GitHub Actions](.github/workflows/ci.yml) runs the build, configuration checks, linting, offline tests, PostgreSQL tests, and DAG checks on pushes and pull requests. Live Eurostat access is an opt-in manual check, so normal CI does not depend on the upstream API. The [hosted GitHub Actions run](https://github.com/hassanzafarr/eurostat-etl-airflow/actions/runs/41716169375) passed all 95 tests, formatting checks, the image build, and initialization against a fresh PostgreSQL database.

See [verification results](docs/VERIFICATION.md) and [operations instructions](docs/OPERATIONS.md) for a fresh-volume check using an isolated Compose project.

## Repository structure

```text
dags/
  eurostat_etl_dag.py       Airflow orchestration
  eurostat/
    config.py              Fixed dataset filters
    etl.py                 Extraction, parser, data contracts
    database.py            Transactional PostgreSQL storage
    schema.sql             Shared idempotent schema
    preview.py             Read-only task-log tables
    metrics.py             SQL-calculated report evidence
    claude.py              Bounded Haiku calls and output checks
    insights.py            Optional reporting and persistent cache
    report.py              HTML/Markdown reports and plots
sql/analysis.sql           SQL examples and economic interpretation
scripts/                   Smoke test, exports, chart generation, screenshots
tests/fixtures/            Synthetic JSON-stat examples
docs/                      Design, dictionary, operations, evidence, charts
.github/workflows/ci.yml   Automated checks
Dockerfile                 Explicit dependency installation
```

## Configuration and scope

`.env.example` documents ports, demo credentials, optional keys, and the log location. Ports bind to localhost. `.env`, execution logs, caches, and local artifacts are ignored by Git. Runtime dependencies are pinned and installed against the Airflow image's constraints; Airflow is pinned explicitly during installation to prevent accidental upgrades.

This is a local portfolio demonstration, not a managed production deployment. It uses one PostgreSQL role, has no external alert delivery, and does not retain raw API payloads or a full revision history. Versions are pinned to the tested runtime; review and upgrade dependencies before any external deployment. Changing a dataset's unit, age, sex, or indicator requires reviewing the table contract and migrating or separating the series.

## Sources and license

Source: European Commission, Eurostat, datasets [nama_10_gdp](https://ec.europa.eu/eurostat/databrowser/view/nama_10_gdp/default/table?lang=en) and [lfsi_emp_a](https://ec.europa.eu/eurostat/databrowser/view/lfsi_emp_a/default/table?lang=en), retrieved via the Statistics API. Consult [Eurostat's reuse notice](https://ec.europa.eu/eurostat/help/copyright-notice) for source-data terms. Charts and CSV files retain source attribution; the code license does not relicense Eurostat data.

Code is licensed under the [MIT License](LICENSE).
