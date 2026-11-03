# Claude Haiku economic reports

The optional `generate_insights` task runs after `preview_data`. It reads a consistent PostgreSQL snapshot, calculates country/year comparisons with SQL, asks Claude for qualitative commentary, validates the result, and renders a standalone HTML report with two plots.

The configured model is **claude-haiku-5-5**, verified against the [official Haiku documentation](https://platform.claude.com/docs/en/models/haiku-5-5/overview). The integration uses the [Messages API](https://platform.claude.com/docs/en/api/messages/create) and [JSON structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), with additional local validation. It uses requests directly; no additional orchestration framework is required.

## Enable live commentary

Add these entries to your private `.env` file at the repository root:

```dotenv
ANTHROPIC_API_KEY=your_private_api_key
ANTHROPIC_MODEL=claude-haiku-5-5
ENABLE_AI_INSIGHTS=true
```

Keep the real key out of chat, Git, screenshots, and documentation. `.env` is ignored and excluded from the Docker build context. Do not put it into `.env.example`. The local key is passed to containers as an environment variable; it is not sent to GitHub Actions.

```bash
docker compose up --build -d
docker compose exec -T airflow-scheduler python scripts/generate_report.py --require-ai
```

This reads existing observations. To rerun ingestion and check all five Airflow tasks:

```bash
docker compose exec -T airflow-scheduler python scripts/smoke_test.py --require-ai
```

## View the result

Open **artifacts/insights/latest.html** on your computer. It contains verified data, model commentary, GDP and employment plots, sources, source flags, and interpretation limits. Plots are embedded, so it can be opened without a web server. The same folder contains:

- `latest.md`: the text report shown in the Airflow task log.
- `latest.json`: evidence, commentary, status, model, timestamps, and token usage for this run.
- `gdp.png` and `employment.png`: standalone plots from the same database snapshot.

In Airflow, select the latest run, then **generate_insights > Logs**, and search for `EUROSTAT ECONOMIC REPORT`. The log shows text; open the HTML file to view plots. The [captured example](AI_REPORT_SAMPLE.md) is a dated real Haiku report, not a live page.

## Grounding and evaluation

SQL computes latest observations and consecutive-year changes. GDP is displayed in billion EUR, with nominal percentage changes. Employment differences are percentage points. Missing preceding years produce no annual comparison. Observation flags are displayed verbatim; Claude does not interpret them.

Claude receives fourteen bounded fact records, not database credentials, raw logs, or SQL execution tools. Each finding references an allowed fact ID and returns a trend direction. The application checks the JSON schema, references, uniqueness, and direction against SQL. Digits and percentages are rejected from model prose; exact numerical evidence is appended by the application. Common causal, ranking, forecasting, and source-status claims are rejected as well.

Twenty-two synthetic golden evaluations cover accepted and rejected outputs: invented years, numeric claims, incorrect directions, unknown or duplicate references, unexpected SQL fields, unsupported causal/ranking wording, and misinterpreted source flags. Mock HTTP tests cover timeouts, refusals, truncation, and provider errors without using a real key.

These are targeted checks, not a proof of every qualitative claim. The HTML report asks readers to review AI prose and makes no causal or forecasting claims. Sources and flags remain visible beside application-rendered numbers.

## Cost control and caching

- Each attempt sends one bounded Messages request, with an output cap of 2,048 tokens and a network timeout.
- No automatic paid retries or silent model switches. The Airflow report task has retries disabled.
- Successful commentary is cached in `eurostat_insight_reports`, keyed by source evidence, model, and prompt version/content. Ingestion timestamps alone do not invalidate it.
- A historical revision, source flag/update change, model change, or prompt change creates a new cache key.
- Cache hits make no request and record zero tokens for the current run. `original_generated_at_utc` preserves generation time.
- Offline and failed reports do not evict successful paid commentary for the same evidence.

Usage depends on your Anthropic account's access and billing. Successful response token counts are recorded; a failed/rejected attempt has unknown token usage rather than a misleading zero. Cache hits record zero tokens. Currency costs are not hard-coded.

## API unavailable or no key

Without a key, the task writes verified tables and plots with `ai_status=not_configured`. Setting `ENABLE_AI_INSIGHTS=false` gives `disabled`. A provider failure or rejected output gives `unavailable`. None of these statuses is described as successful AI generation. Source-data loading remains committed, and the Airflow task can succeed by producing the clearly labelled fallback artifact.

Use `--require-ai` when a check must fail unless validated live or cached commentary exists. For an explicit offline report:

```bash
docker compose exec -T airflow-scheduler python scripts/generate_report.py --offline
```

Storage/rendering errors still fail the report task visibly. A separate manual question DAG is now available; see [Ask Eurostat](ASK_EUROSTAT.md). Continuous multi-turn chat, autonomous repair, and an interactive BI server remain separate future extensions.
