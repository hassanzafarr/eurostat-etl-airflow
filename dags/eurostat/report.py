"""Render verified numbers, Claude commentary and plots as a standalone report."""

import base64
import html
import io
import json
import os
import tempfile
from pathlib import Path

LIMITATIONS = [
    "GDP uses current prices. Its change is nominal, not inflation-adjusted growth.",
    "Employment covers ages 15-64, both sexes. Rate differences are percentage points.",
    "Annual observations are checked for updates daily; these are not daily measurements.",
    "The EU aggregate overlaps the selected countries and must not be added to their totals.",
    "Source flags can mark provisional values, estimates or breaks in series. Check source metadata before drawing conclusions.",
    "Numerical evidence and trend labels are validated. Qualitative AI wording still requires human review; this report establishes no causes or forecasts.",
]


def chart_images(history):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    result = {}
    colors = {
        "DE": "#2563eb",
        "FR": "#db6d28",
        "IT": "#17936d",
        "ES": "#9457b5",
        "NL": "#b28b10",
        "PL": "#a86449",
        "EU27_2020": "#334155",
    }
    from eurostat.metrics import COUNTRIES

    for indicator in ("gdp", "employment"):
        with plt.rc_context({"font.size": 10, "font.family": "DejaVu Sans"}):
            fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
            rows = history[indicator]
            if indicator == "gdp":
                selected = [row for row in rows if row["country_code"] == "DE"]
                ax.plot(
                    [row["year"] for row in selected],
                    [float(row["value"]) for row in selected],
                    color=colors["DE"],
                    marker="o",
                    linewidth=2.5,
                )
                ax.set_title("Germany GDP at current prices", loc="left", fontweight="bold", pad=16)
                ax.set_ylabel("Billion EUR")
                ax.set_ylim(bottom=0)
            else:
                for geo, color in colors.items():
                    selected = [row for row in rows if row["country_code"] == geo]
                    if selected:
                        ax.plot(
                            [row["year"] for row in selected],
                            [float(row["value"]) for row in selected],
                            label=COUNTRIES[geo],
                            color=color,
                            linestyle="--" if geo == "EU27_2020" else "-",
                            linewidth=2,
                        )
                ax.set_title(
                    "Employment rate: ages 15-64, both sexes", loc="left", fontweight="bold", pad=16
                )
                ax.set_ylabel("Employed share of population (%)")
                ax.set_ylim(0, 100)
                ax.legend(frameon=False, ncol=3, fontsize=8, loc="lower left")
            ax.set_xlabel("Observation year")
            ax.grid(axis="y", alpha=0.15)
            ax.spines[["top", "right"]].set_visible(False)
            buffer = io.BytesIO()
            fig.savefig(buffer, format="png", dpi=140)
            plt.close(fig)
            result[indicator] = base64.b64encode(buffer.getvalue()).decode("ascii")
    return result


def evidence_sentence(fact):
    change = "No consecutive previous-year comparison available."
    if fact["change"] is not None:
        change = f"Change versus {fact['previous_year']}: {fact['change']} {fact['change_unit']}."
    return (
        f"{fact['country']} | {fact['year']} | {fact['value']} {fact['unit']}. "
        f"{change} Source flag: {fact['source_status'] or 'none supplied'}."
    )


def render_markdown(report):
    lines = [
        "# Eurostat economic report",
        "",
        f"AI status: {report['ai_status']}",
        f"Model: {report['model']}",
        f"Cached commentary: {report['cached']}",
        f"Report created (UTC): {report['created_at_utc']}",
        "",
    ]
    by_id = {fact["id"]: fact for fact in report["evidence"]["facts"]}
    if report["commentary"]:
        lines += [report["commentary"]["summary"], "", "## Evidence-linked findings", ""]
        for finding in report["commentary"]["findings"]:
            fact = by_id[finding["fact_id"]]
            lines += [
                f"- {finding['commentary']}",
                f"  {evidence_sentence(fact)}",
                f"  Source: {fact['source_url']}",
            ]
    else:
        lines += [
            "AI commentary was not generated. The verified data and charts remain available.",
            report.get("notice", ""),
            "",
        ]
    lines += ["", "## Verified latest observations", ""]
    for fact in by_id.values():
        lines.append(f"- {evidence_sentence(fact)} Source: {fact['source_url']}")
    lines += ["", "## Interpretation limits", "", *[f"- {text}" for text in LIMITATIONS]]
    return "\n".join(lines) + "\n"


def render_html(report, images):
    esc = html.escape
    by_id = {fact["id"]: fact for fact in report["evidence"]["facts"]}
    if report["commentary"]:
        introduction = f"<p>{esc(report['commentary']['summary'])}</p>"
        findings = "".join(
            f"<section class='finding'><h3>{esc(by_id[f['fact_id']]['country'])}: {esc(by_id[f['fact_id']]['indicator'].upper())}</h3>"
            f"<p>{esc(f['commentary'])}</p><p class='evidence'>{esc(evidence_sentence(by_id[f['fact_id']]))}</p>"
            f"<a href='{esc(by_id[f['fact_id']]['source_url'], quote=True)}'>Eurostat source</a></section>"
            for f in report["commentary"]["findings"]
        )
    else:
        introduction = f"<p>AI commentary is unavailable. These tables and plots are calculated from PostgreSQL.</p><p>{esc(report.get('notice', ''))}</p>"
        findings = ""
    rows = "".join(
        f"<tr><td>{esc(f['country'])}</td><td>{esc(f['indicator'].upper())}</td><td>{f['year']}</td>"
        f"<td>{esc(f['value'])}</td><td>{esc(f['unit'])}</td><td>{esc(f['change'] or 'N/A')} {esc(f['change_unit'])}</td>"
        f"<td>{esc(f['source_status'] or '-')}</td></tr>"
        for f in by_id.values()
    )
    caveats = "".join(f"<li>{esc(text)}</li>" for text in LIMITATIONS)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">
<title>Eurostat economic report</title><style>
body{{margin:0;background:#f3f6fa;color:#17324d;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1120px;margin:auto;padding:36px 24px}}h1{{font-size:38px;line-height:1.15;margin:16px 0}}
h2{{margin-top:36px}}.tag{{background:#dbeafe;color:#1649a0;border-radius:30px;padding:6px 14px;display:inline-block}}
.meta{{color:#52677c;font-size:14px}}.finding,figure,.panel{{background:white;border:1px solid #dce5ef;border-radius:12px;padding:22px;margin:18px 0}}
.evidence{{background:#f1f5f9;padding:14px;font-size:14px}}a{{color:#1456b8}}img{{width:100%;height:auto}}
figure{{margin:20px 0}}figcaption{{font-size:13px;color:#52677c}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #dce5ef}}.scroll{{overflow-x:auto}}
</style></head><body><main><span class="tag">SQL evidence + Claude Haiku</span>
<h1>European economic indicators</h1>
<p class="meta">AI status: <strong>{esc(report['ai_status'])}</strong> · Model: {esc(report['model'])} · Cached: {report['cached']}<br>
Created UTC: {esc(report['created_at_utc'])} · Latest ingestion UTC: {esc(str(report['evidence']['latest_ingestion_utc']))}</p>
<div class="panel">{introduction}</div>{findings}
<h2>Charts from the same database snapshot</h2>
<figure><img alt="Germany GDP at current prices" src="data:image/png;base64,{images['gdp']}"><figcaption>Eurostat nama_10_gdp · Current prices; not inflation-adjusted.</figcaption></figure>
<figure><img alt="Employment rate across selected geographies" src="data:image/png;base64,{images['employment']}"><figcaption>Eurostat lfsi_emp_a · Annual observations; source flags remain in the evidence below.</figcaption></figure>
<h2>Verified latest observations</h2><div class="panel scroll"><table><thead><tr><th>Geography</th><th>Indicator</th><th>Year</th><th>Value</th><th>Unit</th><th>Annual change</th><th>Flag</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Interpretation limits</h2><ul>{caveats}</ul>
<p class="meta">Numbers and plots come from SQL evidence. AI prose is descriptive commentary, not an independently verified economic explanation.</p>
</main></body></html>"""


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        temporary = Path(output.name)
        output.write(content)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_report(report, directory):
    directory = Path(directory)
    images = chart_images(report["evidence"]["history"])
    directory.mkdir(parents=True, exist_ok=True)
    for indicator, image in images.items():
        (directory / f"{indicator}.png").write_bytes(base64.b64decode(image))
    atomic_write(directory / "latest.json", json.dumps(report, indent=2) + "\n")
    atomic_write(directory / "latest.md", render_markdown(report))
    atomic_write(directory / "latest.html", render_html(report, images))
    return directory / "latest.html"
