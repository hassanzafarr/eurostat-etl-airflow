CREATE TABLE IF NOT EXISTS eurostat_gdp (
    geo TEXT NOT NULL,
    time_period TEXT NOT NULL,
    value NUMERIC,
    unit TEXT,
    na_item TEXT,
    dataset TEXT,
    snapshot_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (geo, time_period, na_item)
);

CREATE TABLE IF NOT EXISTS eurostat_employment (
    geo TEXT NOT NULL,
    time_period TEXT NOT NULL,
    value NUMERIC,
    unit TEXT,
    na_item TEXT,
    dataset TEXT,
    snapshot_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (geo, time_period)
);

CREATE INDEX IF NOT EXISTS idx_gdp_geo ON eurostat_gdp(geo);
CREATE INDEX IF NOT EXISTS idx_emp_geo ON eurostat_employment(geo);

-- Backward-compatible upgrade for the original local demo.
ALTER TABLE eurostat_gdp ADD COLUMN IF NOT EXISTS dataset TEXT;
ALTER TABLE eurostat_employment ADD COLUMN IF NOT EXISTS dataset TEXT;
ALTER TABLE eurostat_employment ADD COLUMN IF NOT EXISTS na_item TEXT;

ALTER TABLE eurostat_gdp ADD COLUMN IF NOT EXISTS source_status TEXT;
ALTER TABLE eurostat_gdp ADD COLUMN IF NOT EXISTS source_updated TEXT;
ALTER TABLE eurostat_employment ADD COLUMN IF NOT EXISTS source_status TEXT;
ALTER TABLE eurostat_employment ADD COLUMN IF NOT EXISTS source_updated TEXT;

-- Optional Claude commentary is cached separately from source observations.
CREATE TABLE IF NOT EXISTS eurostat_insight_reports (
    report_key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    ai_status TEXT NOT NULL CHECK (ai_status IN ('generated', 'not_configured', 'disabled', 'unavailable')),
    report JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
