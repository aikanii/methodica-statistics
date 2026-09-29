# Methodica

[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/ui-React%20%2B%20Vite-61DAFB?logo=react&logoColor=111)](https://react.dev/)
[![Stats](https://img.shields.io/badge/stats-SciPy%20%7C%20statsmodels%20%7C%20pingouin-0F4C5C)](#statistical-engine)

Evidence-first statistical analysis workbench.

Upload a dataset, state a research question in plain language, and Methodica selects a method, checks assumptions, computes the result with established scientific libraries, validates it, and writes a reproducible report. It will not invent a p-value.

```
data → evidence → method → assumptions → calculation → validation → interpretation
```

---

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Use cases](#use-cases)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Install](#install)
- [Run](#run)
- [Usage](#usage)
- [Bundled samples](#bundled-samples)
- [HTTP API](#http-api)
- [Statistical engine](#statistical-engine)
- [Integrity rules](#integrity-rules)
- [Configuration](#configuration)
- [Development](#development)
- [Limitations](#limitations)
- [License](#license)

---

## Overview

Methodica is for analysts who need a **defensible** result: students, researchers, scientists, and people who should not have to memorize a decision tree of tests.

It is not a chat wrapper around a CSV. The recommender is deterministic. Charts and numbers come from pandas / SciPy / statsmodels / scikit-learn / pingouin / lifelines. Cleaning is never applied silently. Every analysis stores provenance so it can be reproduced.

**Typical path**

1. Load a table (file, SQL, or bundled sample).
2. Review the quality report; accept or reject proposed fixes.
3. Ask a question, or pick a method directly.
4. Inspect assumptions, statistics, effect sizes, and warnings.
5. Export HTML, Markdown, DOCX, PDF, or Excel.

No account is required. The UI opens into a local guest workspace.

---

## Features

| Area | Capability |
| --- | --- |
| Ingest | CSV, Excel, JSON, Parquet, TSV, SQLite, SQL extracts; multi-file concat |
| Profiling | dtypes, roles, missingness, duplicates, constants, ID-like columns, quality score |
| Quality | Issue list with severity, explanation, suggested fix, and preview — propose, do not mutate |
| Cleaning | Impute, drop, coerce, winsorize, encode, transform; versioned; undo / restore |
| EDA | Descriptives, frequencies, histograms, box/violin, scatter, Q–Q, heatmaps, time series |
| Recommender | Maps a natural-language question → method, variables, rationale, alternatives |
| Assumptions | Normality, Levene, cell counts, VIF, heteroscedasticity, PH, sphericity, n, missingness |
| Inference | Tests, ANOVA, regression, GLM, time series, PCA/clustering, survival, reliability, power |
| Validation | Small-n, failed assumptions, tiny effects, causation warnings, numeric cross-checks |
| Assistant | Answers only from computed output |
| Autopilot | Full pipeline with every step visible and overridable |
| Reports | Academic / business / scientific / general · HTML, MD, DOCX, PDF, XLSX, CSV, JSON |
| Repro | Dataset version, params, assumptions, software version, timestamp; replay endpoint |

---

## Use cases

| Domain | Example question |
| --- | --- |
| Environmental science | Is PM2.5 different between urban and rural monitors? |
| Clinical / experimental | Does the intervention change follow-up score? Time-to-event by arm? |
| Psychometrics | Is this Likert scale internally consistent? |
| Coursework / thesis | Which test do I use, and what assumptions failed? |
| Business analytics | Are conversion or spend associated with a segment — and how large is the effect? |
| Data engineering | Is this extract clean enough to model? |

---

## Architecture

```
┌──────────────────────────────────────────┐
│  frontend/     React 18 · Vite 6 · TW    │
│                /api  ──proxy──► :8000    │
└────────────────────┬─────────────────────┘
                     │ REST JSON
┌────────────────────▼─────────────────────┐
│  backend/app   FastAPI                   │
│    routers     ingest, profile, quality  │
│    services    recommend, assumptions    │
│                stats_engine, validate    │
│                reports, autopilot        │
└────────┬───────────────┬─────────────────┘
         │               │
         ▼               ▼
   SQLite + Parquet   SciPy / statsmodels
   storage/           scikit-learn / pingouin
                      lifelines
```

The assistant is **not** an LLM call. It dispatches to the same engine the Analyze page uses.

---

## Repository layout

```text
.
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── sample_data/              # generated on first boot if missing
│   └── app/
│       ├── main.py               # HTTP API
│       ├── auth.py               # optional JWT; guest if unsigned
│       ├── config.py
│       ├── db.py
│       ├── models.py             # SQLAlchemy
│       ├── sample_gen.py
│       └── services/
│           ├── profile.py
│           ├── quality.py
│           ├── cleaning.py
│           ├── recommend.py      # question → method
│           ├── assumptions.py
│           ├── stats_engine.py   # method registry
│           ├── validate.py
│           ├── visualize.py
│           ├── reports.py
│           ├── assistant.py
│           └── autopilot.py
├── frontend/
│   ├── package.json
│   └── src/
│       ├── api.js
│       ├── App.jsx
│       ├── state.jsx
│       ├── components.jsx
│       └── pages/
└── storage/                      # created at runtime (db, uploads, reports)
```

---

## Requirements

| Runtime | Version |
| --- | --- |
| Python | 3.11+ (developed on 3.13) |
| Node.js | 20+ |
| OS | Linux / macOS / Windows (WSL fine) |

Optional: a SQLAlchemy-compatible database URL if you do not want SQLite.

---

## Install

```bash
git clone <repo-url> methodica
cd methodica

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cd frontend && npm install && cd ..
```

---

## Run

Two processes:

```bash
# terminal 1 — API
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# terminal 2 — UI
cd frontend
npm run dev
```

| Service | Default URL |
| --- | --- |
| UI | http://localhost:5173 |
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |

Vite proxies `/api` to the backend. Do not point the browser at `localhost:8000` for the UI.

Health check:

```bash
curl -s http://127.0.0.1:8000/api/health
# {"ok": true, "app": "Methodica", "version": "1.0.0"}
```

---

## Usage

1. Open the UI. No sign-in.
2. **Data → Load sample** (or drop a file).
3. Read **Quality**. Accept, skip, or undo cleaning. Versions are listed under **History**.
4. **Analyze**: paste a research question → **Recommend a method** → inspect / override → **Run analysis**.
5. Or **Models** for a named method (regression, ARIMA, Cox, Cronbach’s α, …).
6. **Autopilot** if you want the full pipeline on one question.
7. **Reports** to export.

Remove a table with **Remove dataset** or the ✕ on the sidebar list.

### Example questions the recommender understands

```text
Is there a significant difference in PM2.5 levels between urban and rural monitoring locations?
Is there a relationship between temperature and PM2.5?
Does the intervention significantly improve performance?
```

Named groups in the question (e.g. urban vs rural) restrict a two-group test to those levels after label standardization.

---

## Bundled samples

Created under `backend/sample_data/` on first API start.

| ID | File | n (approx.) | Notes |
| --- | --- | --- | --- |
| `air` | `air_quality.csv` | 720 | PM2.5/PM10, weather, location; injected NAs, duplicates, bad labels |
| `clinical` | `clinical_trial.csv` | 260 | Treatment, scores, `survival_days`, `event` |
| `survey` | `survey_items.csv` | 180 | Eight Likert items + group |

```bash
curl -X POST http://127.0.0.1:8000/api/datasets/sample/air
```

---

## HTTP API

Auth is optional. Missing/invalid Bearer tokens map to a local guest user.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/auth/me` | Current (or guest) user |
| `GET` | `/api/datasets` | List |
| `POST` | `/api/datasets/upload` | `multipart/form-data` field `files` |
| `POST` | `/api/datasets/from-sql` | `{ url, query, table?, name? }` |
| `POST` | `/api/datasets/sample/{air\|clinical\|survey}` | Load demo table |
| `GET` | `/api/datasets/{id}` | Metadata |
| `DELETE` | `/api/datasets/{id}` | Drop table, versions, analyses, files |
| `GET` | `/api/datasets/{id}/preview` | Paginated rows |
| `GET` | `/api/datasets/{id}/profile` | Column profiles + quality score |
| `GET` | `/api/datasets/{id}/quality` | Issues + proposed operations |
| `POST` | `/api/datasets/{id}/clean` | `{ operations: [{ operation, ... }] }` |
| `POST` | `/api/datasets/{id}/undo` | Previous version |
| `POST` | `/api/datasets/{id}/restore` | `{ version }` |
| `POST` | `/api/datasets/{id}/explore` | EDA payload + charts |
| `POST` | `/api/datasets/{id}/chart` | `{ kind, x, y, ... }` Plotly JSON |
| `GET` | `/api/methods` | Registry (id, family, needs) |
| `POST` | `/api/datasets/{id}/recommend` | `{ question, hint? }` |
| `POST` | `/api/datasets/{id}/assumptions` | `{ method, params }` |
| `POST` | `/api/datasets/{id}/analyze` | `{ method, params, question? }` |
| `POST` | `/api/datasets/{id}/autopilot` | `{ question }` |
| `POST` | `/api/datasets/{id}/assistant` | `{ question }` |
| `POST` | `/api/datasets/{id}/report` | `{ question, style, format }` |
| `GET` | `/api/analyses` | History |
| `POST` | `/api/analyses/{id}/reproduce` | Replay |
| `GET` | `/api/reports/{id}/download` | File |

`POST /analyze` response shape:

```json
{
  "analysis_id": "...",
  "result": {
    "method": "independent_t",
    "method_label": "Independent-samples t-test (Welch)",
    "summary": "t(...) = ..., p = ..., d = ...",
    "statistics": {},
    "interpretation": "...",
    "tables": {},
    "formula": "..."
  },
  "assumptions": [{ "name": "", "status": "pass|fail|warning|assumed|info", "evidence": "", "recommended_action": "" }],
  "validation": { "ok": true, "flags": [] },
  "provenance": {},
  "chart": { "kind": "box", "plotly": {} }
}
```

Cleaning operation names: `drop_duplicates`, `drop_columns`, `drop_rows_missing`, `impute`, `impute_all`, `to_numeric`, `parse_dates`, `strip`, `normalize_case`, `winsorize`, `clip_nonnegative`, `transform`, `encode`, `rename`, `filter`.

---

## Statistical engine

Registry: `backend/app/services/stats_engine.py` (`REGISTRY`, `METHOD_META`). Add a function, register it, declare `needs`.

| Family | `method` ids |
| --- | --- |
| Descriptive | `descriptive`, `frequency` |
| Normality | `shapiro_wilk`, `anderson_darling`, `kolmogorov_smirnov` |
| Correlation | `pearson`, `spearman`, `kendall`, `correlation_matrix` |
| Association | `chi_square`, `fisher_exact`, `cramers_v` |
| Tests | `one_sample_t`, `independent_t`, `paired_t`, `z_test`, `mannwhitney`, `wilcoxon`, `kruskal`, `friedman` |
| ANOVA | `oneway_anova`, `twoway_anova`, `repeated_anova`, `ancova`, `tukey_hsd`, `levene` |
| Regression | `linear_regression`, `multiple_regression`, `polynomial_regression`, `logistic_regression`, `poisson_regression`, `negative_binomial`, `robust_regression` |
| Time series | `trend_analysis`, `moving_average`, `acf_pacf`, `arima`, `sarima`, `exp_smoothing`, `seasonality` |
| Multivariate | `pca`, `factor_analysis`, `manova`, `kmeans`, `lda` |
| Nonparametric | `bootstrap_ci`, `permutation_test` |
| Survival | `kaplan_meier`, `logrank`, `cox_ph` |
| Reliability | `cronbach_alpha` |
| Design | `effect_size`, `power_analysis`, `sample_size` |

Libraries are the source of truth for algorithms. Methodica owns selection, assumptions, validation text, and provenance.

---

## Integrity rules

Enforced in the assistant, reports, and validation layer:

- Do not invent results, datasets, or citations.
- Do not claim significance without a computed p-value on the working table.
- Do not rewrite engine output.
- Report effect size and CI with the test.
- State that association is not causation.
- Surface assumption evidence next to the result.
- Keep a technical error behind a readable message (`title`, `message`, `technical`).

---

## Configuration

`backend/app/config.py`:

| Key | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///storage/methodica.db` | SQLAlchemy URL |
| `UPLOADS` | `storage/uploads` | Versioned Parquet |
| `REPORTS` | `storage/reports` | Generated files |
| `MAX_UPLOAD_MB` | `80` | Upload cap |
| `MAX_PREVIEW_ROWS` | `200` | Preview page size |
| `SECRET_KEY` | dev string | JWT signing (change in production) |

Frontend proxy: `frontend/vite.config.js` → `http://127.0.0.1:8000`.

Production notes: bind the API to an internal host, serve the Vite build behind the same origin as `/api`, replace `SECRET_KEY`, and point `DATABASE_URL` at PostgreSQL if you need concurrent writers.

---

## Development

```bash
# API with reload
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# UI
cd frontend && npm run dev
```

Smoke:

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s -X POST http://127.0.0.1:8000/api/datasets/sample/air
curl -s -X POST http://127.0.0.1:8000/api/datasets/<id>/recommend \
  -H 'Content-Type: application/json' \
  -d '{"question":"Is there a relationship between temperature and PM2.5?"}'
```

New statistical method:

1. Implement `def my_method(df, params) -> dict` in `stats_engine.py` using `result(...)`.
2. Add to `REGISTRY` and `METHOD_META`.
3. Wire variables in `recommend.py` if it should be auto-selected.
4. Add assumption checks in `assumptions.py` if the method has any.

UI pages live under `frontend/src/pages/`. Shared controls: `components.jsx`. REST client: `api.js`.

---

## Limitations

- Not a certified medical device; not a substitute for a statistician on high-stakes work.
- Default DB is SQLite. Swap the URL for PostgreSQL; schema is SQLAlchemy.
- Analyses run in-process. Profile large files before fitting heavy models.
- ARIMA orders default to `(1,1,1)` unless you pass `order`.
- Recommender is a typed decision tree, not an LLM. That is intentional.

---

## License

If this tree includes a `LICENSE` file, that license applies. Otherwise treat the source as available for evaluation and internal use until a license is added.

---

Methodica 1.0.0 · `GET /api/health`
