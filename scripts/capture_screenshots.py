"""Capture real Airflow pages for documentation using an optional headless browser."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--username", default="airflow")
    parser.add_argument("--password", default="airflow")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run_id = args.run_id or json.loads((root / "docs/verification.json").read_text())["run_id"]
    destination = root / "docs/images"
    destination.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    grid = base + "/dags/eurostat_economic_indicators/grid?"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(base + "/login/", wait_until="networkidle")
        page.locator("#username").fill(args.username)
        page.locator("#password").fill(args.password)
        page.locator("input[type=submit]").click()
        page.wait_for_load_state("networkidle")
        page.goto(grid + urlencode({"dag_run_id": run_id}), wait_until="networkidle")
        page.get_by_text("Graph", exact=True).click(timeout=20000)
        page.get_by_text("PythonOperator", exact=True).first.wait_for(state="visible")
        page.screenshot(path=str(destination / "airflow-workflow.png"), full_page=True)
        page.goto(
            grid + urlencode({"dag_run_id": run_id, "task_id": "preview_data", "tab": "logs"}),
            wait_until="networkidle",
        )
        page.get_by_text("========== END DATA PREVIEW ==========", exact=False).wait_for(
            state="visible", timeout=20000
        )
        page.screenshot(path=str(destination / "airflow-preview.png"), full_page=True)
        browser.close()
    print("Saved authenticated workflow and preview screenshots in docs/images")


if __name__ == "__main__":
    main()
