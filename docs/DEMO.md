# A 90-second project demonstration

1. **Purpose (15 seconds):** The pipeline collects official European GDP and employment statistics and produces validated tables for SQL analysis.
2. **Architecture (15 seconds):** Show the README diagram. Eurostat supplies data; Python transforms and validates it; PostgreSQL stores it; Airflow schedules and monitors the tasks.
3. **Workflow (20 seconds):** Select the latest successful run. Show create_tables feeding independent GDP and employment branches, with preview_data waiting for both.
4. **Result (15 seconds):** Open preview_data logs and show country figures, record counts, and Germany GDP history. Show one chart.
5. **Reliability (20 seconds):** Explain primary keys and conflict updates. Show the rollback test and CI workflow. Distinguish locally verified commands from hosted CI, which is pending publication.
6. **Tradeoff (5 seconds):** Every run refreshes a small historical window to capture revisions. Observations are annual; execution is daily.

## CV wording

Built a Dockerized ETL pipeline using Python, Apache Airflow, and PostgreSQL to ingest and validate Eurostat GDP and employment data, with transactional upserts, retries, source metadata, automated tests, and reproducible analysis charts.

## Repository metadata for later publication

Suggested name: eurostat-etl-airflow

Description: Reproducible Eurostat GDP and employment ETL with Python, Airflow, PostgreSQL, Docker, validation, transactional upserts, and automated tests.

Topics: python, apache-airflow, postgresql, docker-compose, etl, data-engineering, eurostat, data-quality

Creating a remote, pushing, pinning the repository, and obtaining a hosted Actions result are publication steps to perform later.
