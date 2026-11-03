"""Optional, cached Claude reports; ingestion remains independent of API availability."""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from psycopg2.extras import Json

from eurostat.claude import (
    DEFAULT_MODEL,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    InsightError,
    request_commentary,
    validate_commentary,
)
from eurostat.database import get_connection
from eurostat.metrics import collect_evidence
from eurostat.report import render_markdown, write_report

logger = logging.getLogger(__name__)


def report_key(evidence, model):
    content = {
        "fingerprint": evidence["fingerprint"],
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "system_prompt": SYSTEM_PROMPT,
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def cached_report(key, connection_factory=None):
    connection = (connection_factory or get_connection)()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT report FROM eurostat_insight_reports WHERE report_key = %s AND ai_status = 'generated'",
                (key,),
            )
            row = cursor.fetchone()
            return row[0] if row else None
    finally:
        connection.close()


def persist_report(report, connection_factory=None):
    # Offline/failure artifacts must not evict a valid, paid generation for the same evidence.
    storage_key = report["report_key"]
    if report["ai_status"] != "generated":
        storage_key += ":" + report["ai_status"]
    connection = (connection_factory or get_connection)()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO eurostat_insight_reports (report_key, model, prompt_version, ai_status, report)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (report_key) DO UPDATE SET
                        ai_status = EXCLUDED.ai_status, report = EXCLUDED.report, updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        storage_key,
                        report["model"],
                        PROMPT_VERSION,
                        report["ai_status"],
                        Json(report),
                    ),
                )
    finally:
        connection.close()


def generate_report(
    evidence, *, api_key, model=DEFAULT_MODEL, enabled=True, cached=None, requester=None
):
    """Pure orchestration for deterministic tests. Cache hits never call the provider."""
    report = {
        "report_key": report_key(evidence, model),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "ai_status": "not_configured",
        "cached": False,
        "generation_attempted": False,
        "tokens_this_run": {"input_tokens": 0, "output_tokens": 0},
        "evidence": evidence,
        "commentary": None,
    }
    if not enabled:
        report.update(ai_status="disabled", notice="AI commentary is disabled by configuration.")
    elif cached and cached.get("report_key") == report["report_key"]:
        try:
            report["commentary"] = validate_commentary(cached["commentary"], evidence["facts"])
            report.update(
                ai_status="generated",
                cached=True,
                original_generated_at_utc=cached.get(
                    "original_generated_at_utc", cached["created_at_utc"]
                ),
            )
        except (InsightError, KeyError, TypeError):
            cached = None
    if enabled and report["commentary"] is None:
        if not api_key.strip():
            report["notice"] = (
                "Add ANTHROPIC_API_KEY to the private local .env file to enable Claude commentary."
            )
        else:
            report["generation_attempted"] = True
            # Failed or rejected responses may still incur usage; do not report a false zero.
            report["tokens_this_run"] = None
            try:
                response = (requester or request_commentary)(evidence["facts"], api_key, model)
                report["commentary"] = validate_commentary(
                    response["commentary"], evidence["facts"]
                )
                report.update(
                    ai_status="generated",
                    tokens_this_run=response["usage"],
                    response_model=response["response_model"],
                )
            except InsightError as exc:
                report.update(ai_status="unavailable", notice=str(exc))
    return report


def generate_insights():
    evidence = collect_evidence()
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    enabled = os.environ.get("ENABLE_AI_INSIGHTS", "true").lower() in ("1", "true", "yes")
    key = report_key(evidence, model)
    cached = cached_report(key) if enabled else None
    report = generate_report(
        evidence,
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        model=model,
        enabled=enabled,
        cached=cached,
    )
    persist_report(report)
    destination = Path(os.environ.get("EUROSTAT_REPORT_DIR", "/opt/airflow/artifacts/insights"))
    path = write_report(report, destination)
    if report["ai_status"] != "generated":
        logger.warning(
            "Claude commentary status: %s. %s", report["ai_status"], report.get("notice", "")
        )
    logger.info(
        "\n========== EUROSTAT ECONOMIC REPORT ==========\n%s\nHTML report: %s\n========== END ECONOMIC REPORT ==========",
        render_markdown(report),
        path,
    )
