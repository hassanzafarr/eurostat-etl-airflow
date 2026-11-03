-- Run: docker compose exec -T postgres psql -U airflow -d eurostat -f /analysis/analysis.sql
-- Or paste each query into a PostgreSQL client connected to eurostat.

-- 1. Dataset coverage. Counts are observations, not number of source API datasets.
SELECT 'GDP' AS dataset, count(*) AS observations, count(DISTINCT geo) AS geographies,
       min(time_period::integer) AS first_year, max(time_period::integer) AS last_year
FROM eurostat_gdp
UNION ALL
SELECT 'Employment', count(*), count(DISTINCT geo), min(time_period::integer), max(time_period::integer)
FROM eurostat_employment;

-- 2. Germany GDP and nominal annual change. Require consecutive calendar years.
WITH history AS (
    SELECT time_period::integer AS year, value,
           lag(value) OVER (ORDER BY time_period::integer) AS previous_value,
           lag(time_period::integer) OVER (ORDER BY time_period::integer) AS previous_year
    FROM eurostat_gdp
    WHERE geo = 'DE' AND unit = 'CP_MEUR' AND na_item = 'B1GQ'
)
SELECT year, round(value / 1000, 2) AS gdp_billion_eur,
       CASE WHEN year = previous_year + 1 THEN
            round(100 * (value / nullif(previous_value, 0) - 1), 2)
       END AS nominal_annual_change_percent
FROM history ORDER BY year;

-- 3. Latest available employment rate per country; retain the observation year.
SELECT DISTINCT ON (geo) geo, time_period::integer AS year,
       value AS employment_rate_percent, source_status
FROM eurostat_employment
WHERE unit = 'PC_POP'
ORDER BY geo, time_period::integer DESC;

-- 4. Germany employment change in percentage points, not percent growth.
WITH history AS (
    SELECT time_period::integer AS year, value,
           lag(value) OVER (ORDER BY time_period::integer) AS previous_value,
           lag(time_period::integer) OVER (ORDER BY time_period::integer) AS previous_year
    FROM eurostat_employment WHERE geo = 'DE'
)
SELECT year, value AS employment_rate_percent,
       CASE WHEN year = previous_year + 1 THEN value - previous_value END AS annual_change_percentage_points
FROM history ORDER BY year;

-- 5. Inspect source flags and ingestion times rather than assuming all figures are final.
SELECT geo, time_period, value, source_status, source_updated, snapshot_ts
FROM eurostat_gdp WHERE source_status IS NOT NULL
ORDER BY time_period::integer DESC, geo;
