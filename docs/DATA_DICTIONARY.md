# Data dictionary

Six countries (`DE`, `FR`, `IT`, `ES`, `NL`, `PL`) plus the EU27_2020 aggregate. Annual observations are requested from 2015 onward. Availability varies with the source; future runs may add years or revise historical values.

| Table | Source | Fixed filters | Primary key |
|---|---|---|---|
| eurostat_gdp | nama_10_gdp | freq=A, na_item=B1GQ, unit=CP_MEUR | geo, time_period, na_item |
| eurostat_employment | lfsi_emp_a | freq=A, indic_em=EMP_LFS, sex=T, age=Y15-64, unit=PC_POP | geo, time_period |

`B1GQ` is gross domestic product. `CP_MEUR` means current prices in million EUR. `EMP_LFS` selects total employment using the LFS resident-population concept; `PC_POP` is percentage of the population within the selected age/sex group. `T` selects both sexes. These filters define each table's contract; the schema is not designed to mix arbitrary age ranges or units.

## Columns

| Column | PostgreSQL type | Meaning |
|---|---|---|
| geo | TEXT, part of primary key | Eurostat geography code |
| time_period | TEXT, part of primary key | Four-digit observation year; cast to integer for sorting |
| value | NUMERIC | Source observation in the specified unit |
| unit | TEXT | CP_MEUR for GDP; PC_POP for employment |
| na_item | TEXT | B1GQ for GDP; null for employment |
| dataset | TEXT | Internal name: gdp or employment |
| snapshot_ts | TIMESTAMP | UTC ingestion time stored without timezone; refreshed by upsert |
| source_status | TEXT, nullable | Original Eurostat observation flag string, such as p or e |
| source_updated | TEXT, nullable | Source update timestamp retained verbatim from the response |

Interpret flags using the source dataset's metadata. Explicit null observations are skipped and logged. An empty response, a missing configured geography, or invalid observations fail validation. Missing years are not invented or interpolated.

## Interpretation

- Divide GDP values by 1,000 to display billion EUR.
- GDP annual change is nominal because the series is at current prices.
- Subtract employment rates to express changes in percentage points.
- The EU aggregate includes the selected member countries; summing it with them double-counts.
- These tables store latest known observations. Upserts replace previous revisions; old versions are not preserved.
- Rows omitted by later responses remain in the database. Use source_updated and snapshot_ts when assessing freshness.
