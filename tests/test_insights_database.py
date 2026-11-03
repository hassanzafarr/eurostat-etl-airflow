"""Check report evidence and persistent caching against a real isolated PostgreSQL schema."""

from unittest.mock import Mock

import pytest
from eurostat.database import load_to_postgres
from eurostat.insights import cached_report, generate_report, persist_report
from eurostat.metrics import collect_evidence
from eurostat.report import write_report
from test_database import frame_for

pytestmark = pytest.mark.integration


def seed(factory):
    for key in ("gdp", "employment"):
        load_to_postgres(frame_for(key), "eurostat_" + key, factory)


def test_sql_metrics_units_changes_and_cache_fingerprint(database):
    seed(database)
    evidence = collect_evidence(database)
    assert len(evidence["facts"]) == 14
    facts = {fact["id"]: fact for fact in evidence["facts"]}
    assert facts["gdp_DE_2024"]["value"] == "1.00"
    assert facts["gdp_DE_2024"]["change"] == "0.10"
    assert facts["employment_DE_2024"]["change"] == "0.10"
    assert facts["employment_DE_2024"]["change_unit"] == "percentage points"
    assert facts["gdp_DE_2024"]["change_unit"] == "nominal percent"
    load_to_postgres(frame_for("gdp"), "eurostat_gdp", database)
    assert collect_evidence(database)["fingerprint"] == evidence["fingerprint"]
    revision = frame_for("gdp")
    revision.loc[0, "value"] = 500
    load_to_postgres(revision, "eurostat_gdp", database)
    assert collect_evidence(database)["fingerprint"] != evidence["fingerprint"]


def test_missing_year_never_becomes_annual_growth(database):
    seed(database)
    connection = database()
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE eurostat_gdp SET time_period = '2021' WHERE time_period = '2023'"
            )
    connection.close()
    facts = collect_evidence(database)["facts"]
    assert all(
        fact["change"] is None and fact["direction"] == "unavailable"
        for fact in facts
        if fact["indicator"] == "gdp"
    )


def test_report_cache_and_rendered_charts(database, tmp_path):
    seed(database)
    evidence = collect_evidence(database)
    commentary = {
        "summary": "The selected annual observations show descriptive movements.",
        "findings": [
            {
                "fact_id": fact["id"],
                "direction": fact["direction"],
                "commentary": "The rate of change follows the supplied comparison.",
            }
            for fact in evidence["facts"][:3]
        ],
    }
    requester = Mock(
        return_value={
            "commentary": commentary,
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "response_model": "claude-haiku-5-5",
        }
    )
    report = generate_report(evidence, api_key="test", requester=requester)
    persist_report(report, database)
    loaded = cached_report(report["report_key"], database)
    requester.reset_mock()
    repeated = generate_report(evidence, api_key="test", requester=requester, cached=loaded)
    assert repeated["cached"]
    requester.assert_not_called()
    path = write_report(repeated, tmp_path)
    assert path.exists()
    output = path.read_text()
    assert output.count("data:image/png;base64,") == 2
    assert (tmp_path / "latest.json").exists() and (tmp_path / "latest.md").exists()


def test_read_only_evidence_does_not_modify_source_tables(database):
    seed(database)
    evidence = collect_evidence(database)
    report = generate_report(evidence, api_key="")
    persist_report(report, database)
    assert cached_report(report["report_key"], database) is None
    assert len(collect_evidence(database)["history"]["gdp"]) == 14


def test_disabled_reports_do_not_evict_paid_cache(database):
    seed(database)
    evidence = collect_evidence(database)
    commentary = {
        "summary": "The recorded annual observations can be compared descriptively.",
        "findings": [
            {
                "fact_id": fact["id"],
                "direction": fact["direction"],
                "commentary": "The observation follows the supplied annual comparison.",
            }
            for fact in evidence["facts"][:3]
        ],
    }
    generated = generate_report(
        evidence,
        api_key="test",
        requester=Mock(
            return_value={
                "commentary": commentary,
                "usage": {},
                "response_model": "claude-haiku-5-5",
            }
        ),
    )
    persist_report(generated, database)
    disabled = generate_report(evidence, api_key="", enabled=False)
    persist_report(disabled, database)
    assert cached_report(generated["report_key"], database)["ai_status"] == "generated"
