"""Airflow graph and import checks; skipped when Airflow is not installed."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.airflow


def test_dag_imports_and_enforces_dependencies():
    pytest.importorskip("airflow")
    from airflow.models import DagBag

    bag = DagBag(dag_folder=str(Path(__file__).parents[1] / "dags"), include_examples=False)
    assert not bag.import_errors, bag.import_errors
    dag = bag.get_dag("eurostat_economic_indicators")
    assert set(dag.task_ids) == {
        "create_tables",
        "etl_gdp",
        "etl_employment",
        "preview_data",
        "generate_insights",
    }
    assert dag.get_task("preview_data").upstream_task_ids == {"etl_gdp", "etl_employment"}
    assert dag.get_task("generate_insights").upstream_task_ids == {"preview_data"}
    assert dag.get_task("generate_insights").retries == 0
    for task_id in ("etl_gdp", "etl_employment"):
        assert dag.get_task(task_id).upstream_task_ids == {"create_tables"}
        assert dag.get_task(task_id).retries == 2
        assert not dag.get_task(task_id).do_xcom_push
    assert not dag.catchup
    assert dag.max_active_runs == 1
