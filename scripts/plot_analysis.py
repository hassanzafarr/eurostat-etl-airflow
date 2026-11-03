"""Render publication figures from committed CSV snapshots; no database required."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
COLORS = {
    "DE": "#2166ac",
    "FR": "#d95f02",
    "IT": "#1b9e77",
    "ES": "#984ea3",
    "NL": "#e6ab02",
    "PL": "#a6761d",
    "EU27_2020": "#344054",
}
NAMES = {
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "PL": "Poland",
    "EU27_2020": "EU aggregate",
}


def read_data(name):
    with (ROOT / "docs" / "data" / f"{name}.csv").open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def style(ax, title, subtitle, ylabel):
    ax.set_title(title, loc="left", fontsize=22, fontweight="bold", pad=44, color="#102a43")
    ax.text(0, 1.04, subtitle, transform=ax.transAxes, fontsize=11, color="#52606d")
    ax.set_ylabel(ylabel, labelpad=12, color="#334e68")
    ax.grid(axis="y", color="#e6edf3", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.tick_params(colors="#52606d", length=0, pad=8)


def save_figure(fig, destination, name):
    fig.savefig(destination / f"{name}.png", dpi=180)
    svg = destination / f"{name}.svg"
    fig.savefig(svg, metadata={"Date": None})
    # Stable IDs and normalized whitespace keep regenerated figures reviewable in Git.
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )


def main():
    images = ROOT / "docs" / "images"
    images.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "figure.facecolor": "white",
            "svg.hashsalt": "eurostat-etl",
        }
    )
    gdp = [row for row in read_data("eurostat_gdp") if row["geo"] == "DE"]
    years = [int(row["time_period"]) for row in gdp]
    values = [float(row["value"]) / 1000 for row in gdp]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    style(
        ax,
        "Germany's GDP at current prices",
        f"{min(years)}-{max(years)} | Annual observations",
        "Billion EUR",
    )
    ax.plot(years, values, color=COLORS["DE"], linewidth=3, marker="o", markersize=5)
    ax.fill_between(years, values, min(values) * 0.92, color=COLORS["DE"], alpha=0.07)
    ax.set_ylim(min(values) * 0.92, max(values) * 1.07)
    ax.set_xticks(years)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.annotate(
        f"{values[-1]:,.2f}",
        (years[-1], values[-1]),
        xytext=(-10, 14),
        textcoords="offset points",
        ha="right",
        color=COLORS["DE"],
        fontweight="bold",
    )
    fig.text(
        0.09,
        0.035,
        "Source: Eurostat, nama_10_gdp. Not inflation-adjusted. The vertical axis starts above zero.\nSnapshot metadata and observation flags: docs/data/eurostat_gdp.csv",
        fontsize=9,
        color="#52606d",
    )
    fig.subplots_adjust(left=0.10, right=0.96, bottom=0.20, top=0.78)
    save_figure(fig, images, "germany-gdp")
    plt.close(fig)
    data = read_data("eurostat_employment")
    fig, ax = plt.subplots(figsize=(11, 6.5))
    style(
        ax,
        "Employment rates across Europe",
        "People aged 15-64 | Both sexes | Annual observations",
        "Employed share of population (%)",
    )
    for geo in COLORS:
        rows = [row for row in data if row["geo"] == geo]
        ax.plot(
            [int(row["time_period"]) for row in rows],
            [float(row["value"]) for row in rows],
            label=NAMES[geo],
            color=COLORS[geo],
            linewidth=2.8 if geo in ("DE", "EU27_2020") else 1.7,
            linestyle="--" if geo == "EU27_2020" else "-",
        )
    ax.set_ylim(0, 100)
    ax.set_xticks(years)
    ax.legend(loc="lower left", ncol=3, frameon=False, fontsize=9)
    fig.text(
        0.09,
        0.035,
        "Source: Eurostat, lfsi_emp_a. EMP_LFS / PC_POP / Y15-64 / T.\nThe EU aggregate overlaps the selected countries; it is not an additional country.",
        fontsize=9,
        color="#52606d",
    )
    fig.subplots_adjust(left=0.10, right=0.96, bottom=0.20, top=0.78)
    save_figure(fig, images, "employment-trends")
    plt.close(fig)
    print("Rendered two analysis figures in docs/images (PNG and SVG)")


if __name__ == "__main__":
    main()
