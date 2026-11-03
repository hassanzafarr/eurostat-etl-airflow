# A 90-second project demonstration

1. **Purpose (15 seconds):** The pipeline collects official European GDP and employment statistics and produces validated tables for SQL analysis.
2. **Architecture (15 seconds):** Show the README diagram. Eurostat supplies data; Python transforms and validates it; PostgreSQL stores it; Airflow schedules and monitors the tasks.
3. **Workflow (20 seconds):** Select the latest successful run. Show create_tables feeding independent GDP and employment branches, with preview_data waiting for both and generate_insights rendering the optional Claude report afterward.
4. **Result (15 seconds):** Open preview_data logs and show country figures, record counts, and Germany GDP history. Open artifacts/insights/latest.html to show Haiku commentary, exact SQL evidence, and plots.
5. **Reliability (20 seconds):** Explain primary keys and conflict updates. Show the rollback test and CI workflow. Show the passing hosted GitHub Actions run and distinguish automated checks from the separate live API test.
6. **Tradeoff (5 seconds):** Every run refreshes a small historical window to capture revisions. Observations are annual; execution is daily.

## CV wording

Built a Dockerized ETL pipeline using Python, Apache Airflow, and PostgreSQL to ingest and validate Eurostat GDP and employment data, with transactional upserts, retries, source metadata, automated tests, and cached Claude Haiku reports grounded in SQL metrics.

## Published repository

https://github.com/hassanzafarr/eurostat-etl-airflow

Name: eurostat-etl-airflow

Description: Reproducible Eurostat GDP and employment ETL with Python, Airflow, PostgreSQL, Docker, validation, transactional upserts, and automated tests.

Topics: python, apache-airflow, postgresql, docker-compose, etl, data-engineering, eurostat, data-quality

The public repository has been created and its description and topics configured.

To feature it on your GitHub profile, open [your profile](https://github.com/hassanzafarr), click **Customize your pins**, select **eurostat-etl-airflow**, and save. GitHub's supported API does not expose profile-pin updates, so this profile action is a manual step. See [GitHub's pinning instructions](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/pinning-items-to-your-profile).
