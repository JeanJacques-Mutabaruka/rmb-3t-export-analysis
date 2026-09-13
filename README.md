# RMB 3T Export Intelligence

**Version V1-0f**

A Streamlit tool that maintains a growing history of Rwanda's 3T (tin, tantalum,
tungsten) mineral export declarations from MCIS extracts, and benchmarks them
two ways:

- **International** — Rwanda's realised prices against LME, USGS and Fastmarkets references.
- **Peer (internal)** — each exporter against the Rwandan market's own average, maximum and minimum.

---

## Run it locally — one command

**macOS / Linux**

```bash
./run.sh
```

**Windows**

```
run.bat
```

That is all. The script creates a virtual environment, installs the
dependencies (first run only, about a minute) and opens the app at
<http://localhost:8501>.

If the script will not run on macOS/Linux, make it executable first:
`chmod +x run.sh`.

**Manual alternative**

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/Home.py
```

Requires Python 3.10 or newer.

### First thing to try

The app ships with an **empty dataset** but with **rules pre-loaded** — the
exclusion rules and name-harmonisation decisions agreed during analysis are
already in `data/`, so nothing needs retyping. Either:

- Press **🧪 LOAD DEMO DATA** on the Home page to explore with synthetic data, or
- Go to **1 · Data Management → Upload & Validate** and upload a real MCIS extract.

---

## Pages

| Page | What it does |
|---|---|
| **Home** | Dataset summary, demo data, unsaved-changes warning |
| **1 · Data Management** | Multi-file upload with per-file validation, conflict resolution, dataset browser, ingestion history, save & commit |
| **2 · Rules & Data Quality** | Name harmonisation proposals and approval, exclusion categories and rules, anomaly suggestions |
| **3 · Market Overview** | Volumes, values, price trends, grade statistics, buyer and destination concentration |
| **4 · International Benchmark** | Price gap, estimated losses, loss share by mineral, benchmark editor |
| **5 · Peer Benchmark** | Basis settings, peer statistics (avg/max/min/range), discounts, value forgone |
| **6 · Exporter Scorecard** | Ranking, worst traders per commodity and year, exporter detail, comparison |
| **7 · Reports & Exports** | Summary report, excluded rows with multi-criteria filtering, export centre, Word/PDF reports |

---

## How persistence works — read this

**Nothing is stored on the server.** The app loads its dataset and rules from
files committed to this repository, and holds any changes you make in the
browser session only.

To make work permanent:

1. Do the work (upload, approve rules, set exclusions).
2. Go to **1 · Data Management → Save & Commit**.
3. Download `dataset.xlsx`, `dataset.json`, and any rules files you changed.
4. Replace the matching files in `data/` in the repository.
5. Commit and push.

A warning banner appears whenever there is unsaved work. If you close the
browser without downloading, that work is gone.

**Or let the app commit for you.** With a GitHub token in Streamlit secrets,
*1 · Data Management → Save & Commit* gains a **Commit directly to GitHub**
section that pushes the changed files itself. See `DEPLOYMENT.md` Part 3.

---

## Repository layout

```
app/            Streamlit UI — pages, styling, formatting, downloads
engine/         Pure-Python calculation engine (no Streamlit imports)
                including github_sync (commit write-back) and reporting (Word/PDF)
data/           Committed dataset and pre-loaded rules files
tests/          pytest regression tests (30)
```

### What ships in `data/`

| File | Contents |
|---|---|
| `dataset.json` / `.xlsx` | **Empty.** No real export data is committed — see the privacy note in `DEPLOYMENT.md`. |
| `rules_exclusions.json` | 6 pre-loaded rules across 4 categories (373 rows excluded on the 2019–2026 extract) |
| `rules_harmonisation.json` | 3 approved buyer merges, 7 never-merge pairs |
| `intl_prices.json` | Full benchmark series with provenance tags |

The engine is deliberately free of Streamlit imports so it can be unit-tested
directly and reused from a script or notebook.

```bash
python -m pytest tests/ -q
```

---

## Key conventions

- **All prices are $/kg of contained metal** (`value ÷ (quantity × grade ÷ 100)`),
  so grade differences never distort a comparison.
- **Peers are exporters shipping the same product** in the same period — not the
  same mineral. Mineral-level grouping would pool 99.9%-grade tin ingots with
  4%-grade tin slag.
- **Minimum is a statistic, not a loss basis.** An exporter is not "losing"
  against the floor; Min is shown for range and error detection.
- **Nothing is excluded automatically.** Anomaly detection proposes; you decide.
- **Nothing is auto-overwritten.** Conflicting duplicates go to a review table.

---

## A caution about the international benchmarks

Reliability is not equal across the three minerals:

| Mineral | Basis | Reliability |
|---|---|---|
| Cassiterite | LME tin cash settlement, monthly | **Solid** — exchange-traded, continuous |
| Coltan | USGS/CRU annual averages, a Nov-2025 anchor, an Argus Feb-2026 spot | **Mixed** — March-2026 onward is held flat and is almost certainly too low |
| Wolframite | USGS annual averages, two Fastmarkets 2026 anchors | **Anchors real**, monthly path between them unknown |

Every benchmark point carries a provenance tag (`REAL`, `INTERPOLATED`,
`ASSUMPTION`, `USER OVERRIDE`) and is shown next to the figure. Any point can be
overridden on **4 · International Benchmark → Benchmark Editor**.

Annual benchmarks applied to monthly data understate within-year swings. The
floored view treats months where Rwanda beat the benchmark as zero loss rather
than a gain — the conservative, defensible choice for reporting.

---

## A caution about the peer benchmark

Trading below the peer average is **not by itself evidence of wrongdoing**.
Contract timing, impurity penalties, lot size, payment terms and long-term
offtake agreements priced off an earlier reference all produce legitimate
discounts. The tool identifies where to look, not what was found.

The **% periods below average** column is the useful signal: a discount
sustained across most periods is a pattern; the same discount in one period may
simply be timing.

---

## Known deviation from the design rules

FinIntel rule **R15** requires DataTables Responsive for tables over 4 columns.
That rule was written for the static HTML site; DataTables cannot be embedded in
Streamlit without losing native sorting, column configuration and theming. This
tool uses `st.dataframe`, which provides equivalent responsive behaviour
natively. Flagged here rather than silently ignored.
