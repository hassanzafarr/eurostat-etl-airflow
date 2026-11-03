"""Offline regression tests using synthetic JSON-stat fixtures."""

import copy
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import requests
from eurostat.config import DATASETS
from eurostat.database import load_to_postgres
from eurostat.etl import DataQualityError, extract_eurostat, parse_jsonstat_to_df, validate_data


@pytest.fixture(params=["gdp", "employment"])
def dataset(request):
    key = request.param
    payload = json.loads((Path(__file__).parent / "fixtures" / f"{key}.json").read_text())
    return key, payload


def test_fixture_decodes_country_year_value_and_flags(dataset):
    key, payload = dataset
    frame = parse_jsonstat_to_df(payload, key)
    validate_data(frame, key)
    assert len(frame) == 14
    assert frame.iloc[0]["geo"] == "DE"
    assert frame.iloc[0]["time_period"] == "2023"
    assert frame.iloc[1]["time_period"] == "2024"
    assert frame.iloc[2]["geo"] == "ES"
    assert frame.iloc[-1]["geo"] == "PL"
    assert frame.iloc[-1]["source_status"] == "e"
    assert frame.iloc[0]["source_status"] == "p"
    assert frame.iloc[0]["source_updated"] == payload["updated"]


def test_dense_and_sparse_encodings_match(dataset):
    key, payload = dataset
    dense = copy.deepcopy(payload)
    dense["value"] = list(payload["value"].values())
    dense["status"] = [payload["status"].get(str(i)) for i in range(14)]
    dense["dimension"]["geo"]["category"]["index"] = list(
        payload["dimension"]["geo"]["category"]["index"]
    )
    expected = parse_jsonstat_to_df(payload, key).drop(columns="snapshot_ts")
    actual = parse_jsonstat_to_df(dense, key).drop(columns="snapshot_ts")
    pd.testing.assert_frame_equal(actual, expected)


def test_null_observations_are_skipped_and_zero_retained(dataset):
    key, payload = dataset
    payload["value"]["0"] = None
    payload["value"]["1"] = 0
    frame = parse_jsonstat_to_df(payload, key)
    assert len(frame) == 13
    assert frame.iloc[0]["value"] == 0
    validate_data(frame, key)


@pytest.mark.parametrize(
    "values", [{}, {"14": 1}, {"-1": 1}, {"0": float("nan")}, {"0": True}, {"0": "oops"}]
)
def test_invalid_observations_fail(dataset, values):
    key, payload = dataset
    payload["value"] = values
    with pytest.raises(DataQualityError):
        parse_jsonstat_to_df(payload, key)


@pytest.mark.parametrize(
    "mutation",
    [
        "unit",
        "missing_country",
        "unexpected_country",
        "negative",
        "year",
        "duplicate",
        "null",
        "dimension",
    ],
)
def test_data_contract_rejects_wrong_series(dataset, mutation):
    key, payload = dataset
    frame = parse_jsonstat_to_df(payload, key)
    if mutation == "unit":
        frame.loc[0, "unit"] = "WRONG"
    elif mutation == "missing_country":
        frame = frame[frame.geo != "DE"]
    elif mutation == "unexpected_country":
        frame.loc[0, "geo"] = "XX"
    elif mutation == "negative":
        frame.loc[0, "value"] = -1
    elif mutation == "year":
        frame.loc[0, "time_period"] = "2024-Q1"
    elif mutation == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    elif mutation == "null":
        frame.loc[0, "time_period"] = None
    else:
        frame.loc[0, "na_item" if key == "gdp" else "age"] = "WRONG"
    with pytest.raises(DataQualityError):
        validate_data(frame, key)


def test_employment_over_100_fails():
    payload = json.loads((Path(__file__).parent / "fixtures/employment.json").read_text())
    frame = parse_jsonstat_to_df(payload, "employment")
    frame.loc[0, "value"] = 101
    with pytest.raises(DataQualityError, match="exceeds 100"):
        validate_data(frame, "employment")


def test_bad_dimensions_fail(dataset):
    key, payload = dataset
    payload["size"][0] = 0
    with pytest.raises(DataQualityError):
        parse_jsonstat_to_df(payload, key)


def test_duplicate_load_rejected_before_connection(dataset):
    key, payload = dataset
    frame = parse_jsonstat_to_df(payload, key).iloc[[0, 0]]
    factory = Mock()
    with pytest.raises(ValueError, match="duplicate"):
        load_to_postgres(frame, DATASETS[key]["table"], factory)
    factory.assert_not_called()


def test_unknown_table_rejected(dataset):
    key, payload = dataset
    with pytest.raises(ValueError, match="Unknown target"):
        load_to_postgres(parse_jsonstat_to_df(payload, key), "untrusted_table")


def test_request_filters_and_timeout(dataset):
    key, payload = dataset
    response = Mock()
    response.json.return_value = payload
    with patch("eurostat.etl.requests.get", return_value=response) as get:
        assert extract_eurostat(key) == payload
    assert get.call_args.kwargs["timeout"] == (10, 90)
    assert get.call_args.kwargs["params"]["geo"] == DATASETS[key]["geos"]
    response.raise_for_status.assert_called_once()


@pytest.mark.parametrize("error", [requests.Timeout("timeout"), requests.HTTPError("503")])
def test_api_failures_are_propagated_for_airflow_retry(error):
    with patch("eurostat.etl.requests.get", side_effect=error), pytest.raises(type(error)):
        extract_eurostat("gdp")


def test_http_error_checked_before_decoding():
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("503")
    with (
        patch("eurostat.etl.requests.get", return_value=response),
        pytest.raises(requests.HTTPError),
    ):
        extract_eurostat("gdp")
    response.json.assert_not_called()


def test_api_error_payload_fails():
    response = Mock()
    response.json.return_value = {"error": "unavailable"}
    with patch("eurostat.etl.requests.get", return_value=response), pytest.raises(DataQualityError):
        extract_eurostat("gdp")
