# Verification record

Verified locally on 3 November 2026 using Docker Desktop with Linux containers on Windows, Python 3.11, Airflow 2.10.2, and PostgreSQL 15.

| Check | Result |
|---|---|
| Explicit Dockerfile dependency installation | Image built successfully |
| Fresh database volume | New eurostat-verify Compose project initialized both databases |
| Offline parser, contract, HTTP and AI tests | 110 cases passed, including 22 golden AI evaluations and controlled Q&A checks |
| Real PostgreSQL integration tests | 9 cases passed, including SQL report metrics and caching |
| Airflow import, dependency and question-form checks | 2 cases passed |
| Complete container test suite | 121 passed |
| Ruff lint and format checks | Passed |
| Initial ETL on a fresh database | Four tasks succeeded before AI reporting was added |
| Updated scheduler workflow with Haiku reporting | Five successful tasks; validated commentary reused from cache |
| Live Claude Haiku request | claude-haiku-5-5 returned a validated report |
| Report plots | HTML contains two rendered plots from the same SQL snapshot |
| Preview retrieval through authenticated Airflow log API | Passed |
| Upgrade of existing local database and real workflow | Passed; 77 records remain in each table |
| Hosted GitHub Actions | [Passed all 95 tests and build checks](https://github.com/hassanzafarr/eurostat-etl-airflow/actions/runs/41716169375) |

[Machine-readable latest result](verification.json) includes the five-task run identifier, AI model/status/cache result, verification timestamp, and dataset coverage. Current screenshots show that successful run. The original fresh-stack check established startup reproducibility; the updated stack retained the existing database and was validated again with Haiku reporting.

The database tests create isolated temporary schemas. They prove repeated loads do not duplicate keys, revised values update, records absent from a partial load remain, source flags survive loading, schema application is repeatable, and a failure on the second insert page rolls back the first page.

## Reproduce the evidence

Use the fresh-volume procedure in [OPERATIONS.md](OPERATIONS.md). Within the selected stack:

```bash
docker compose exec -T airflow-scheduler python scripts/smoke_test.py --output docs/verification.json
docker compose exec -T airflow-scheduler python scripts/export_data.py
```

The `--output` option deliberately replaces the documentation's verification snapshot. Use the complete `-p eurostat-verify -f docker-compose.yml -f compose.verify.yml` prefix when checking the disposable stack.

For charts, install requirements-analysis.txt in your host Python environment and run scripts/plot_analysis.py. PNG and SVG artifacts are generated from committed CSV files, not synthetic test fixtures.

For optional screenshots, install requirements-screenshots.txt, run `python -m playwright install chromium`, then run:

```bash
python scripts/capture_screenshots.py --base-url http://localhost:18080
```

Use the correct base URL and run identifier for the stack whose evidence you want to capture. A run ID from the fresh verification database will not exist in another database. Browser sessions are headless; cookies and passwords are not saved into the repository.

## Boundaries

This is one successful source snapshot plus automated regressions, not proof of production uptime or performance at large scale. Ordinary CI uses synthetic API fixtures so source downtime or revisions do not destabilize unrelated code checks. Live source access is tested separately.

## AI evaluation evidence

The AI tests cover numeric-prose rejection, evidence IDs, trend directions, causal/ranking wording, source-flag interpretation, truncation/refusals, API error redaction, provider unavailability, disabled/missing-key reports, historical revisions, missing-year comparisons, and persistent caching. A real Haiku request was reviewed, and the subsequent scheduler run reused validated commentary with zero API tokens for that run. The captured sample and report screenshot are in AI_REPORT_SAMPLE.md.

## Manual question form

The ask_eurostat form was verified in the live Airflow UI. A real Haiku question about Germany GDP between 2015 and 2025 succeeded, returning an application-calculated nominal change of 46.39% with exact endpoint values and a source link. Repeating the same question used the cache with zero provider tokens. Tests cover bounded plans, disallowed SQL/indicators/countries, missing years/endpoints, percent versus percentage-point changes, citation validation, unavailable credentials, and cache invalidation.
