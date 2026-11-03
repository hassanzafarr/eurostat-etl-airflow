"""Exercise a real scheduled run, verify readable logs, and restore pause state."""

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from eurostat.database import get_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://airflow-webserver:8080")
    parser.add_argument("--username", default="airflow")
    parser.add_argument("--password", default="airflow")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    session = requests.Session()
    session.auth = (args.username, args.password)
    base = args.base_url.rstrip("/") + "/api/v1/dags/eurostat_economic_indicators"

    def api(method, path="", **kwargs):
        response = session.request(method, base + path, timeout=15, **kwargs)
        response.raise_for_status()
        return response.json()

    deadline = time.monotonic() + 90
    while True:
        try:
            state = api("GET")
            tasks = api("GET", "/tasks")["tasks"]
            if len(tasks) == 4:
                break
        except requests.RequestException:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError("Airflow API or DAG did not become ready")
        time.sleep(3)
    run_id = "portfolio_validation_" + uuid.uuid4().hex[:10]
    api("POST", "/dagRuns", json={"dag_run_id": run_id})
    try:
        api("PATCH", json={"is_paused": False})
        deadline = time.monotonic() + 120
        while True:
            run = api("GET", "/dagRuns/" + run_id)
            print(run_id, run["state"], flush=True)
            if run["state"] in ("success", "failed") or time.monotonic() > deadline:
                break
            time.sleep(3)
        if run["state"] != "success":
            raise RuntimeError(f"Workflow did not succeed: {run['state']}")
    finally:
        api("PATCH", json={"is_paused": state["is_paused"]})
    tasks = api("GET", "/dagRuns/" + run_id + "/taskInstances")["task_instances"]
    assert len(tasks) == 4 and all(task["state"] == "success" for task in tasks)
    response = session.get(
        base + "/dagRuns/" + run_id + "/taskInstances/preview_data/logs/1",
        params={"full_content": "true"},
        timeout=15,
    )
    response.raise_for_status()
    log = (
        response.json()["content"]
        if "application/json" in response.headers.get("Content-Type", "")
        else response.text
    )
    assert all(
        section in log
        for section in (
            "EUROSTAT DATA PREVIEW",
            "Employment rate",
            "Germany GDP",
            "END DATA PREVIEW",
        )
    )
    connection = get_connection()
    summaries = {}
    try:
        with connection.cursor() as cursor:
            for table in ("eurostat_gdp", "eurostat_employment"):
                cursor.execute(
                    f"SELECT count(*), count(DISTINCT geo), min(time_period), max(time_period) FROM {table}"
                )
                count, geos, first, last = cursor.fetchone()
                summaries[table] = {
                    "observations": count,
                    "geographies": geos,
                    "first_year": first,
                    "last_year": last,
                }
    finally:
        connection.close()
    report = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "state": run["state"],
        "tasks": {task["task_id"]: task["state"] for task in tasks},
        "preview_log_verified": True,
        "schedule_paused": api("GET")["is_paused"],
        "datasets": summaries,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
