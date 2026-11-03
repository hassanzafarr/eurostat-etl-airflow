# Draft project announcement

I built an end-to-end batch ETL pipeline for European economic indicators using Python, Apache Airflow, PostgreSQL, and Docker Compose.

It fetches GDP and employment data from Eurostat, decodes JSON-stat responses, validates the selected series, and loads observations with transactional PostgreSQL upserts. Historical refreshes pick up revised figures without creating duplicate records.

The project includes independent Airflow tasks, retries, data previews, synthetic API fixtures, PostgreSQL integration tests, and reproducible SQL analysis and charts. An optional Claude Haiku task now produces economic commentary linked to verified SQL facts, with persistent caching, structured output checks, and a standalone report with plots. Tests cover revised observations, history preservation, and rollback when an insert batch fails.

One useful lesson: a run can appear successful while loading no useful data unless source responses and expected dimensions are explicitly validated. I added checks for countries, units, annual periods, observation keys, and employment-rate bounds.

The demonstration covers six countries plus the EU aggregate. GDP uses current prices, so changes are nominal rather than inflation-adjusted.

Repository: https://github.com/hassanzafarr/eurostat-etl-airflow

#DataEngineering #Python #ApacheAirflow #PostgreSQL #ETL

The expanded local suite passes 95 tests, including 22 golden evaluations of AI output. Check the latest GitHub Actions result before posting a hosted-CI claim. Before posting, attach the workflow screenshot and one chart.
