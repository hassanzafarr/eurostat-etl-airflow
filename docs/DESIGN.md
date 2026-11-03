# Design decisions and limits

## Why these components

Python handles HTTP and JSON-stat data. pandas supports validation and tabular inspection. PostgreSQL provides numeric storage, primary keys, transactional writes, and conflict updates. Airflow supplies dependencies, scheduling, retries, execution timeouts, and task logs. Docker Compose makes the tested runtime accessible without installing Airflow directly on Windows.

For this small workload a scheduled Python script would also be viable. Airflow was chosen to demonstrate orchestration and recovery across independent datasets. LocalExecutor avoids a broker and separate worker service for two ETL branches.

## Task boundaries

Each dataset is a single ETL task, with schema preparation before both and a preview afterward. This keeps raw payloads and pandas frames out of XCom. A retry repeats extraction and transformation; idempotent upserts make repeated writes safe. Separate extraction and transformation tasks would require durable intermediate storage, which this demo does not currently need.

The parser and loader are reusable modules tested independently of Airflow. One schema.sql serves initial startup, the DAG, and database tests.

## Historical refresh and revisions

Every execution requests data from 2015 onward. This is a bounded historical refresh with upserts, not incremental extraction or destructive table replacement. Older years can be revised, so requesting only the latest year could miss corrections. At the current scale, full extraction is simple. Larger implementations could use revision metadata, partitioned windows, and raw archives.

Daily scheduling checks for source updates to annual observations. The DAG uses UTC, catchup=False, and max_active_runs=1. Enabling a DAG can schedule the latest eligible interval.

## Consistency

A dataset load is atomic across insert batches. GDP and employment are independent transactions; they do not commit together. If one fails, the other's successful commit remains. The preview requires both to succeed and uses a repeatable-read, read-only transaction.

Rows missing from a later response are retained. This preserves prior observations but means source deletions require explicit reconciliation. source_status and source_updated retain upstream context. snapshot_ts records ingestion, not when the economic event happened.

## Validation policy

Fail for empty datasets, incorrect filters, missing configured geographies, duplicate keys, invalid annual periods, non-finite/negative values, or employment rates above 100%. Preserve source flags and skip explicit null observations. Missing years are allowed because availability can differ; no values are imputed. A fixed 77-row count is not a permanent data contract.

## Deployment boundaries

The pinned Airflow 2.10.2 / Python 3.11 runtime reproduces the demonstration; no claim is made that these are the latest supported versions. Review and upgrade dependencies before deployment. Ports bind to localhost; keys and credentials are environment-configurable. One local role owns both databases.

There is no cloud deployment, external failure notification, raw-payload archive, historical revision store, role-separated access control, or cross-dataset atomic publication. The data preview is a task-log report. The optional Claude task adds validated commentary and plots to a standalone HTML artifact; there is no interactive BI server.

## Future extensions

Raw-object storage, run audit tables, revision history, atomic publication through run identifiers, alert delivery, a reviewed supported Airflow release, and an interactive analytics dashboard. These are future work, not implemented features.

## Optional AI reporting

The fifth task uses SQL-derived evidence and calls Claude Haiku with a bounded structured-output request. Numbers and sources are rendered by the application; AI text references known facts and must pass schema, direction, and prose checks. Qualitative wording still requires human review. Source flags are shown verbatim rather than interpreted by the model.

A persistent cache includes historical source content, flags, update metadata, model and prompt settings. It excludes ingestion timestamps. No automatic paid retries are made. Missing credentials and rejected/unavailable output create a clearly labelled data-and-plot report, keeping source ingestion independent of provider availability. Storage/rendering failures remain visible as task failures. See AI_INTEGRATION.md for controls and limits.
