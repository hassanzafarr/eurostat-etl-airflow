"""Offline Claude evaluations and report behavior; no real API credentials required."""

import copy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from eurostat.claude import DEFAULT_MODEL, InsightError, request_commentary, validate_commentary
from eurostat.insights import generate_report, report_key
from eurostat.report import render_html, render_markdown

FIXTURE = json.loads((Path(__file__).parent / "fixtures/insight_evaluations.json").read_text())
FACTS = FIXTURE["facts"]
VALID = FIXTURE["cases"][0]["output"]


def evidence():
    return {
        "facts": copy.deepcopy(FACTS),
        "fingerprint": "synthetic-fixture",
        "history": {},
        "latest_ingestion_utc": "2026-01-01T00:00:00+00:00",
    }


def provider_result():
    return {
        "commentary": copy.deepcopy(VALID),
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "response_model": DEFAULT_MODEL,
    }


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["name"])
def test_golden_grounding_evaluations(case):
    if case["valid"]:
        assert validate_commentary(case["output"], FACTS) == case["output"]
    else:
        with pytest.raises(InsightError):
            validate_commentary(case["output"], FACTS)


def test_without_key_report_is_honest_and_no_request_occurs():
    requester = Mock()
    report = generate_report(evidence(), api_key="", requester=requester)
    assert report["ai_status"] == "not_configured"
    assert report["commentary"] is None
    assert "AI commentary was not generated" in render_markdown(report)
    requester.assert_not_called()


def test_explicitly_disabled_never_contacts_provider():
    requester = Mock()
    report = generate_report(
        evidence(), api_key="fake-private-key", enabled=False, requester=requester
    )
    assert report["ai_status"] == "disabled"
    requester.assert_not_called()


def test_cache_hit_makes_no_paid_request_and_preserves_origin_time():
    requester = Mock(return_value=provider_result())
    initial = generate_report(evidence(), api_key="fake-private-key", requester=requester)
    requester.reset_mock()
    second = generate_report(
        evidence(), api_key="fake-private-key", cached=initial, requester=requester
    )
    assert second["cached"] and second["ai_status"] == "generated"
    assert second["tokens_this_run"] == {"input_tokens": 0, "output_tokens": 0}
    assert second["original_generated_at_utc"] == initial["created_at_utc"]
    requester.assert_not_called()


def test_model_and_source_changes_invalidate_cache():
    original = generate_report(
        evidence(), api_key="test", requester=Mock(return_value=provider_result())
    )
    changed = evidence()
    changed["fingerprint"] = "source-revised"
    requester = Mock(return_value=provider_result())
    report = generate_report(changed, api_key="test", cached=original, requester=requester)
    assert not report["cached"]
    requester.assert_called_once()
    assert report_key(changed, DEFAULT_MODEL) != report_key(changed, "claude-haiku-other")


def test_api_failure_preserves_verified_report():
    requester = Mock(side_effect=InsightError("Claude request could not complete"))
    report = generate_report(evidence(), api_key="test", requester=requester)
    assert report["ai_status"] == "unavailable"
    assert report["evidence"]["facts"] == FACTS
    assert report["generation_attempted"] and report["tokens_this_run"] is None
    assert report["commentary"] is None
    assert "1234.00" in render_markdown(report)


def test_wrong_model_output_is_not_published():
    result = provider_result()
    result["commentary"]["findings"][0]["direction"] = "decreased"
    report = generate_report(evidence(), api_key="test", requester=Mock(return_value=result))
    assert report["ai_status"] == "unavailable"
    assert report["commentary"] is None


def test_html_escapes_model_text_and_numbers_come_from_evidence():
    result = provider_result()
    result["commentary"]["summary"] = "<script>alert('unsafe')</script>"
    report = generate_report(evidence(), api_key="test", requester=Mock(return_value=result))
    output = render_html(report, {"gdp": "", "employment": ""})
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert "1234.00" in output and "75.00" in output
    assert "default-src 'none'" in output


def test_http_contract_uses_selected_haiku_and_bounded_input():
    response = Mock(status_code=200)
    response.json.return_value = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": json.dumps(VALID)}],
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "model": DEFAULT_MODEL,
    }
    post = Mock(return_value=response)
    result = request_commentary(FACTS, "test-private-key", post=post)
    assert result["commentary"] == VALID
    url = post.call_args.args[0]
    assert url == "https://api.anthropic.com/v1/messages"
    arguments = post.call_args.kwargs
    assert arguments["json"]["model"] == DEFAULT_MODEL
    assert arguments["json"]["max_tokens"] == 2048
    assert "temperature" not in arguments["json"]
    assert "test-private-key" not in json.dumps(arguments["json"])
    assert arguments["timeout"] == (10, 90)


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_failures_never_echo_provider_body_or_api_key(status):
    response = Mock(status_code=status, text="test-private-key")
    with pytest.raises(InsightError) as error:
        request_commentary(FACTS, "test-private-key", post=Mock(return_value=response))
    assert "test-private-key" not in str(error.value)
    response.json.assert_not_called()


def test_network_failure_is_redacted():
    with pytest.raises(InsightError) as error:
        request_commentary(
            FACTS, "test-private-key", post=Mock(side_effect=requests.Timeout("test-private-key"))
        )
    assert "test-private-key" not in str(error.value)


@pytest.mark.parametrize("reason", ["max_tokens", "refusal", "tool_use"])
def test_truncated_or_refused_response_rejected(reason):
    response = Mock(status_code=200)
    response.json.return_value = {"stop_reason": reason, "content": []}
    with pytest.raises(InsightError):
        request_commentary(FACTS, "test", post=Mock(return_value=response))
