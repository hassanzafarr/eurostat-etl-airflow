# Verification record

Verified locally on 3 November 2026 using Docker Desktop with Linux containers on Windows, Python 3.11, Airflow 2.10.2, and PostgreSQL 15.

| Check | Result |
|---|---|
| Explicit Dockerfile dependency installation | Image built successfully |
| Fresh database volume | New eurostat-verify Compose project initialized both databases |
| Offline parser, contract, and HTTP tests | 47 cases passed |
| Real PostgreSQL integration tests | 4 cases passed |
| Airflow import and dependency checks | 1 case passed |
| Complete container test suite | 52 passed |
| Ruff lint and format checks | Passed |
| Actual scheduler-run workflow on fresh data | Four successful tasks |
| Preview retrieval through authenticated Airflow log API | Passed |
| Upgrade of existing local database and real workflow | Passed; 77 records remain in each table |
| Hosted GitHub Actions | Pending publication; no remote run claimed |

[Machine-readable fresh-stack result](verification.json) includes the run identifier, task states, verification timestamp, and dataset coverage. Screenshots show the actual successful run from that fresh stack. The original stack retained its existing database volume and was also validated after the update.

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
