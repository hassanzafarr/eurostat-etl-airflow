"""Eurostat JSON-stat extraction and data contracts, independent of Airflow."""

import logging
from datetime import datetime, timezone
from math import isfinite, prod

import pandas as pd
import requests

from eurostat.config import BASE_URL, DATASETS

logger = logging.getLogger(__name__)


class DataQualityError(ValueError):
    """An upstream response or observation does not satisfy the dataset contract."""


def extract_eurostat(dataset_key: str) -> dict:
    config = DATASETS[dataset_key]
    params = {**config["params"], "geo": config["geos"]}
    logger.info("Extracting %s from dataset %s", dataset_key, config["code"])
    response = requests.get(f"{BASE_URL}/{config['code']}", params=params, timeout=(10, 90))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("class") != "dataset":
        raise DataQualityError(f"Expected a JSON-stat dataset for {dataset_key}")
    return payload


def parse_jsonstat_to_df(payload: dict, dataset_key: str) -> pd.DataFrame:
    """Decode sparse/dense row-major values and preserve Eurostat observation flags."""
    ids, sizes = payload.get("id", []), payload.get("size", [])
    if (
        not ids
        or len(ids) != len(sizes)
        or len(set(ids)) != len(ids)
        or any(type(size) is not int or size <= 0 for size in sizes)
    ):
        raise DataQualityError("Invalid or empty JSON-stat dimensions")
    if not {"geo", "time", "unit"}.issubset(ids):
        raise DataQualityError("Missing required geo, time or unit dimension")
    mappings = {}
    try:
        for dimension, size in zip(ids, sizes):
            index = payload["dimension"][dimension]["category"]["index"]
            mapping = (
                dict(enumerate(index))
                if isinstance(index, list)
                else {v: k for k, v in index.items()}
            )
            if set(mapping) != set(range(size)):
                raise DataQualityError(f"Invalid category positions for {dimension}")
            mappings[dimension] = mapping
    except (KeyError, AttributeError, TypeError) as exc:
        raise DataQualityError("Invalid dimension category metadata") from exc
    values = payload.get("value", {})
    if not isinstance(values, (list, dict)):
        raise DataQualityError("Expected a dense array or sparse value object")
    observations = enumerate(values) if isinstance(values, list) else values.items()
    status = payload.get("status", {})
    rows = []
    missing = 0
    for position, value in observations:
        try:
            flat_index = int(position)
            if not 0 <= flat_index < prod(sizes):
                raise DataQualityError(f"Observation index {position} outside the dataset")
            if value is None:
                missing += 1
                continue
            if isinstance(value, bool) or not isfinite(float(value)):
                raise DataQualityError(f"Invalid observation at {position}")
            row = {"value": float(value)}
            for dimension, size in reversed(list(zip(ids, sizes))):
                flat_index, coordinate = divmod(flat_index, size)
                row[dimension.lower()] = mappings[dimension][coordinate]
            if isinstance(status, dict):
                row["source_status"] = status.get(str(position))
            elif isinstance(status, list):
                row["source_status"] = (
                    status[int(position)] if int(position) < len(status) else None
                )
            else:
                raise DataQualityError("Invalid observation status metadata")
            rows.append(row)
        except (TypeError, ValueError, OverflowError) as exc:
            raise DataQualityError(f"Invalid observation at index {position}: {exc}") from exc
    if not rows:
        raise DataQualityError(f"No observations for {dataset_key}; check API filters")
    frame = pd.DataFrame(rows).rename(columns={"time": "time_period"})
    frame["dataset"] = dataset_key
    frame["snapshot_ts"] = datetime.now(timezone.utc).replace(tzinfo=None)
    frame["source_updated"] = payload.get("updated")
    if "na_item" not in frame:
        frame["na_item"] = None
    logger.info(
        "Parsed %s observations for %s; skipped %s explicit nulls", len(frame), dataset_key, missing
    )
    return frame


def validate_data(frame: pd.DataFrame, dataset_key: str):
    """Reject incorrect series, incomplete geography coverage and invalid values before loading."""
    config = DATASETS[dataset_key]
    required = {"geo", "time_period", "value", "unit", "dataset", "snapshot_ts"}
    required.update(k for k in config["params"] if k not in {"format", "lang", "sinceTimePeriod"})
    if frame.empty or not required.issubset(frame.columns):
        raise DataQualityError(
            f"Empty data or missing required columns: {sorted(required - set(frame.columns))}"
        )
    if frame[list(required)].isna().any().any():
        raise DataQualityError("Null required fields")
    if set(frame["geo"]) != set(config["geos"]):
        raise DataQualityError("Unexpected or missing countries")
    if set(frame["dataset"]) != {dataset_key}:
        raise DataQualityError("Dataset identifier mismatch")
    for dimension, expected in config["params"].items():
        if dimension not in {"format", "lang", "sinceTimePeriod"} and set(frame[dimension]) != {
            expected
        }:
            raise DataQualityError(f"Unexpected {dimension}; expected {expected}")
    year_text = frame["time_period"].astype(str)
    if not year_text.str.fullmatch(r"[0-9]{4}").all():
        raise DataQualityError("Invalid annual time period")
    years = year_text.astype(int)
    if (
        (years < int(config["params"]["sinceTimePeriod"]))
        | (years > datetime.now(timezone.utc).year)
    ).any():
        raise DataQualityError("Time period outside the requested annual range")
    numeric = pd.to_numeric(frame["value"], errors="coerce")
    if not numeric.map(lambda value: isfinite(value) and value >= 0).all():
        raise DataQualityError("Non-finite or negative observations")
    if dataset_key == "employment" and (numeric > 100).any():
        raise DataQualityError("Employment percentage exceeds 100")
    keys = ["geo", "time_period"] + (["na_item"] if dataset_key == "gdp" else [])
    if frame.duplicated(keys).any():
        raise DataQualityError("Duplicate observation keys: check for unfiltered series")
    logger.info(
        "Validated %s: %s observations, %s geographies, years %s-%s",
        dataset_key,
        len(frame),
        frame.geo.nunique(),
        years.min(),
        years.max(),
    )
