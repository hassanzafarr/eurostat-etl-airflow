"""Generate a report from stored observations without rerunning extraction."""

import argparse
import json
import os
from pathlib import Path

from eurostat.database import create_tables
from eurostat.insights import generate_insights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Generate verified tables and plots without calling Claude",
    )
    parser.add_argument(
        "--require-ai",
        action="store_true",
        help="Fail if live or cached validated commentary is unavailable",
    )
    args = parser.parse_args()
    if args.offline:
        os.environ["ENABLE_AI_INSIGHTS"] = "false"
    create_tables()
    generate_insights()
    report_path = (
        Path(os.environ.get("EUROSTAT_REPORT_DIR", "/opt/airflow/artifacts/insights"))
        / "latest.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if args.require_ai and report["ai_status"] != "generated":
        raise SystemExit(
            "Verified data and plots are available, but Claude commentary was not generated. Check the report notice."
        )


if __name__ == "__main__":
    main()
