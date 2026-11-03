# Running and troubleshooting

## Start, inspect and stop

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 airflow-init airflow-scheduler airflow-webserver
```

Successful initialization exits with code 0. The init container is not a continuously running worker.

```bash
docker compose stop        # Stop processes, retaining containers and data
docker compose start       # Resume stopped containers
docker compose down        # Remove containers/network, retaining the database volume
```

Do not add `--volumes` to the main stack's shutdown unless you intend to erase its database.

## Health and smoke check

Open http://localhost:8080/health. metadatabase and scheduler should be healthy. A null triggerer status is expected: this DAG does not use deferrable operators and no triggerer service is configured.

```bash
docker compose exec -T airflow-scheduler python scripts/smoke_test.py
```

The script triggers a real manual run, temporarily unpauses the DAG if required, checks four successful tasks and readable preview logs, and restores its original pause state. Use username/password arguments for customized credentials.

## Fresh database verification

A separate project name creates a separate named database volume. The override uses UI port 18080 and PostgreSQL port 55432. It requires a recent Docker Compose supporting `!override`.

```powershell
$env:AIRFLOW_LOG_DIR = './artifacts/verify-logs'
docker compose -p eurostat-verify -f docker-compose.yml -f compose.verify.yml up --build -d
docker compose -p eurostat-verify -f docker-compose.yml -f compose.verify.yml exec -T -e TEST_DATABASE_URL=postgresql://airflow:airflow@postgres:5432/eurostat airflow-scheduler python -m pytest -q tests
docker compose -p eurostat-verify -f docker-compose.yml -f compose.verify.yml exec -T airflow-scheduler python scripts/smoke_test.py
```

Clean up only this disposable project's services and database after verification:

```powershell
docker compose -p eurostat-verify -f docker-compose.yml -f compose.verify.yml down --volumes
Remove-Item Env:\AIRFLOW_LOG_DIR
```

On macOS/Linux, use `export AIRFLOW_LOG_DIR=./artifacts/verify-logs` and `unset AIRFLOW_LOG_DIR` instead of the PowerShell environment commands. Verification shares source code with the main stack, with a distinct database and log folder. Use matching password settings if you customized .env.

## Common issues

| Symptom | Action |
|---|---|
| Docker cannot connect to its engine | Start Docker Desktop and select Linux containers. |
| Port already allocated | Change AIRFLOW_WEB_PORT or POSTGRES_PORT in .env and recreate the affected service. |
| Password mismatch after editing .env | Existing volumes retain the old password; an environment change does not rotate the database role password. |
| Tasks do not run | Check scheduler health, enable the DAG, and select the correct run. |
| Empty response or missing geography | Inspect task logs and source metadata; resolve the source/filter issue rather than bypassing validation. |
| Python dependency missing | Update pinned requirements, rebuild, and recreate services. |
| Connections table omits eurostat_postgres | Environment-supplied connections do not appear there. |
| Old run lacks preview_data | Select a run created after the task was introduced. |

Compare logs, schedules, and exported metadata in UTC. The UI can display a selected local timezone.
