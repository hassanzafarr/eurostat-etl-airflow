"""Controlled question planning, grounded answers, and unavailable-data behavior."""

import copy
from unittest.mock import Mock

import pytest
from eurostat.claude import DEFAULT_MODEL, InsightError
from eurostat.questions import (
    ask,
    execute_plan,
    question_key,
    render_answer,
    validate_answer,
)


def evidence():
    history = {"gdp": [], "employment": []}
    facts = []
    for indicator in history:
        for geo, country, values in [("DE", "Germany", [1000, 1500]), ("FR", "France", [500, 750])]:
            for index, year in enumerate([2015, 2025]):
                raw = str(values[index] if indicator == "gdp" else 70 + index)
                row = {
                    "country_code": geo,
                    "country": country,
                    "year": year,
                    "value": str(values[index] / 1000) if indicator == "gdp" else raw,
                    "raw_value": raw,
                    "source_status": None,
                    "source_updated": "synthetic",
                    "previous_year": 2015 if index else None,
                    "change": None,
                }
                history[indicator].append(row)
            facts.append(
                {
                    **history[indicator][-1],
                    "id": f"{indicator}_{geo}_2025",
                    "indicator": indicator,
                    "unit": "billion EUR, current prices"
                    if indicator == "gdp"
                    else "percent of population aged 15-64, both sexes",
                    "change_unit": "nominal percent" if indicator == "gdp" else "percentage points",
                    "source_url": "https://ec.europa.eu/eurostat/",
                }
            )
    return {
        "history": history,
        "facts": facts,
        "fingerprint": "synthetic",
        "latest_ingestion_utc": "2026-01-01T00:00:00+00:00",
    }


def plan(action="compare", **changes):
    return {
        "action": action,
        "indicators": ["employment"],
        "countries": ["DE", "FR"],
        "start_year": None,
        "end_year": 2025,
        "reason": "none",
        **changes,
    }


def test_comparison_returns_exact_requested_year():
    rows = execute_plan(plan(), evidence())
    assert len(rows) == 2 and {row["year"] for row in rows} == {2025}
    assert rows[0]["value"] == "71"


def test_historical_change_uses_exact_raw_values_and_distinct_units():
    gdp = execute_plan(
        plan("change", indicators=["gdp"], countries=["DE"], start_year=2015), evidence()
    )[0]
    employment = execute_plan(plan("change", countries=["DE"], start_year=2015), evidence())[0]
    assert gdp["change"] == "50.00" and gdp["start_value"] == "1.0"
    assert gdp["change_unit"] == "nominal percent"
    assert employment["change"] == "1.00" and employment["change_unit"] == "percentage points"


def test_missing_endpoint_never_uses_another_year():
    assert (
        execute_plan(
            plan("change", indicators=["gdp"], countries=["DE"], start_year=2016), evidence()
        )
        == []
    )
    assert execute_plan(plan(end_year=2026), evidence()) == []


def test_trend_keeps_available_rows_without_imputation():
    rows = execute_plan(plan("trend", countries=["DE"], start_year=2015), evidence())
    assert [row["year"] for row in rows] == [2015, 2025]


@pytest.mark.parametrize(
    "changes",
    [
        {"countries": ["UK"]},
        {"countries": ["DE", "DE"]},
        {"countries": []},
        {"indicators": ["inflation"]},
        {"indicators": ["gdp", "gdp"]},
        {"sql": "DROP TABLE eurostat_gdp"},
        {"start_year": 2026, "end_year": 2015},
        {"start_year": 1800},
        {"reason": "outside_dataset"},
    ],
)
def test_invalid_plans_cannot_execute(changes):
    with pytest.raises(InsightError):
        execute_plan(plan(**changes), evidence())


def test_successful_answer_is_cached_without_api_calls():
    source = evidence()
    selected = execute_plan(plan(), source)
    requester = Mock(
        side_effect=[
            {"output": plan(), "usage": {"input_tokens": 10, "output_tokens": 20}},
            {
                "output": {
                    "answer": "The selected countries have matching recorded rates in this comparison.",
                    "citations": [row["id"] for row in selected],
                },
                "usage": {"input_tokens": 30, "output_tokens": 40},
            },
        ]
    )
    result = ask("Compare Germany and France employment.", source, "test", requester=requester)
    assert result["status"] == "answered" and requester.call_count == 2
    assert result["tokens_this_run"] == {"input_tokens": 40, "output_tokens": 60}
    requester.reset_mock()
    repeated = ask(
        "Compare Germany and France employment.", source, "test", requester=requester, cached=result
    )
    assert repeated["cached"]
    assert repeated["tokens_this_run"] == {"input_tokens": 0, "output_tokens": 0}
    requester.assert_not_called()
    assert "2025" in render_answer(result) and "Source:" in render_answer(result)


def test_unavailable_year_needs_no_second_provider_call():
    requester = Mock(return_value={"output": plan(end_year=2026), "usage": {}})
    result = ask("Compare employment in 2026.", evidence(), "test", requester=requester)
    assert result["status"] == "no_data"
    requester.assert_called_once()


@pytest.mark.parametrize(
    "reason",
    ["unsupported_country", "unsupported_indicator", "causal_or_forecast", "outside_dataset"],
)
def test_out_of_scope_questions_are_explained_without_data_or_second_request(reason):
    requester = Mock(
        return_value={
            "output": plan(
                "unsupported",
                countries=[],
                indicators=[],
                start_year=None,
                end_year=None,
                reason=reason,
            ),
            "usage": {},
        }
    )
    result = ask("Explain the requested subject.", evidence(), "test", requester=requester)
    assert result["status"] == "unsupported" and result["notice"]
    assert result["facts"] == []
    requester.assert_called_once()


@pytest.mark.parametrize(
    "answer",
    [
        {"answer": "The rate was 99%.", "citations": ["fake"]},
        {"answer": "The result is descriptive.", "citations": ["fake"]},
        {"answer": "It changed because of policy.", "citations": []},
    ],
)
def test_ungrounded_answers_are_rejected(answer):
    with pytest.raises(InsightError):
        validate_answer(answer, execute_plan(plan(), evidence()))


def test_no_key_never_calls_provider():
    requester = Mock()
    with pytest.raises(InsightError, match="ANTHROPIC_API_KEY"):
        ask("Compare Germany employment.", evidence(), "", requester=requester)
    requester.assert_not_called()


def test_answer_can_mention_verified_years_but_not_other_numbers():
    facts = execute_plan(
        plan("change", indicators=["gdp"], countries=["DE"], start_year=2015), evidence()
    )
    valid = {
        "answer": "Germany's GDP increased between 2015 and 2025.",
        "citations": [facts[0]["id"]],
    }
    assert validate_answer(valid, facts) == valid
    with pytest.raises(InsightError):
        validate_answer({**valid, "answer": "GDP rose by 99 percent between 2015 and 2025."}, facts)


def test_cache_invalidates_on_question_model_and_evidence_change():
    source = evidence()
    key = question_key("Compare employment", source, DEFAULT_MODEL)
    changed = copy.deepcopy(source)
    changed["fingerprint"] = "updated"
    assert question_key("Compare GDP", source, DEFAULT_MODEL) != key
    assert question_key("Compare employment", changed, DEFAULT_MODEL) != key
    assert question_key("Compare employment", source, "claude-haiku-other") != key
