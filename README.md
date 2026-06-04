# TLF Studio

Internal web application for Crinetics biostatisticians and clinical
programmers to configure, generate, preview, and manage clinical TLF
(Tables, Listings, Figures) outputs for clinical study reports.

TLF Studio sits on top of the standalone
[`crinetics-tlf-automation`](../crinetics-tlf-automation) Python library —
all aggregation, formatting, and RTF generation lives there. Studio adds:

- Per-study configuration via a guided wizard (ADaM upload, SAP import,
  arms, analysis sets)
- AI-assisted SAP extraction with editable, source-cited results
- AI-assisted TFL selection (natural language → shell diff)
- Real-data table preview rendered as HTML alongside an AI chat panel
- Anomaly detection (deterministic rules + AI augmentation)
- Async generation via Celery / Redis with live status
- Output management with audit trail and approval workflow

---

## Requirements

Before setting up, make sure you have the following installed:

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| uv | any | https://docs.astral.sh/uv/ — or run `pip install uv` |
| Node.js | 20+ | https://nodejs.org/ |
| Git | any | https://git-scm.com/ |

You also need both repos cloned as siblings in the same parent folder:

```
C:\crinetics\
  ├── crinetics-tlf-automation\   ← the TLF library
  └── crinetics-tlf-studio\       ← this app
```

---

## First-time setup

Do this once after cloning. You will not need to repeat it.

**Step 1 — Clone both repos**

```cmd
mkdir C:\crinetics
cd C:\crinetics
git clone <crinetics-tlf-automation repo URL>
git clone <crinetics-tlf-studio repo URL>
```

**Step 2 — Install backend dependencies**

```cmd
cd C:\crinetics\crinetics-tlf-studio\backend
uv sync
```

This creates a `.venv` folder inside `backend\` with all Python dependencies installed.

**Step 3 — Install frontend dependencies**

```cmd
cd C:\crinetics\crinetics-tlf-studio\frontend
npm install
```

**Step 4 — Configure your environment**

The file `backend\.env` already exists with the correct paths pre-configured.
The only thing you need to add is your Anthropic API key (required for AI features
such as SAP extraction, table chat, and anomaly detection).

Open `backend\.env` in any text editor and fill in:

```
ANTHROPIC_API_KEY=your-key-here
```

Get a key from https://console.anthropic.com/. If you skip this step the app
still runs — AI features will just return an error when used.

---

## Launching the app

Once first-time setup is complete, launching takes one step:

**Double-click `launch.bat`** in the `crinetics-tlf-studio\` folder.

Two minimised terminal windows will appear in the taskbar (the API server and
the frontend). After about 8 seconds your browser will open automatically to:

**http://localhost:3000**

### To shut down

Close the two minimised terminal windows in the taskbar labelled
**TLF API** and **TLF Frontend**.

### Optional — desktop shortcut

Right-click `launch.bat` → **Send to → Desktop (create shortcut)** for
one-click launch from your desktop.

---

## Architecture

```
                  ┌──────────────────────┐
                  │  Next.js Frontend    │  (App Router, TypeScript,
                  │  http://:3000        │   Tailwind, shadcn-style,
                  └──────────┬───────────┘   React Query, Zustand)
                             │ REST + streaming
                             ▼
                  ┌──────────────────────┐
                  │  FastAPI Backend     │  (Python 3.11+, Pydantic)
                  │  http://:8000        │
                  └──┬───────────┬───────┘
                     │           │
       ┌─────────────▼─┐   ┌────▼──────────┐
       │  Anthropic    │   │  Celery Worker│  (Redis broker)
       │  Claude       │   └─────┬─────────┘
       └───────────────┘         │
                                 ▼
                     ┌───────────────────────┐
                     │ crinetics-tlf-        │  (the actual TLF
                     │ automation library    │   library, imported)
                     └──────────┬────────────┘
                                │
                                ▼
                     ./studies/{uuid}/
                       ├── study_meta.json
                       ├── study_config.yaml
                       ├── data/
                       ├── outputs/
                       └── audit/
```

Each study lives entirely on disk under `STUDIES_ROOT/<uuid>/`. There is
no database — `study_meta.json` and `study_config.yaml` are the source of
truth.

> **Note:** TLF generation runs synchronously (`TLF_JOB_EXECUTOR=inline`)
> by default, so Redis and Celery are not required. To switch to async
> parallel generation, install Redis and set `TLF_JOB_EXECUTOR=celery`
> in `backend\.env`.

---

## First-use walkthrough

1. **Create a study** — click "New Study" from the dashboard.
2. **Step 1: Upload data.** Drop in your ADaM parquet (or .sas7bdat /
   .xpt) files. The backend identifies each domain by filename and
   extracts:
   - STUDYID
   - Treatment arms from ADSL.TRT01P / TRT01PN
   - Analysis-set N counts per arm from SAFFL / ITTFL / EFFFL
   - Visit schedule and PARAMCDs available per domain
3. **Step 2: Configuration.** Edit auto-detected fields. Reorder
   treatment arms (drag handle) to control output column order.
4. **Step 3: SAP import.** Drop in the SAP PDF. AI extracts SAP
   definitions and proposes which optional tables to include, each with
   source-cited excerpts you can verify. You can skip this step.
5. **Step 4: Review & create.** Confirms what we'll write to
   `study_config.yaml`, then opens the study overview.
6. **Select TFLs.** Required tables are always on; conditional tables
   auto-select based on uploaded data (e.g. fatal AE table only if
   DTHFL='Y' exists). Use the natural-language input ("Add the DILI plot
   and remove ECG tables") to apply bulk changes.
7. **Preview a table.** Click any table's Preview button. The backend
   runs the full polars aggregation against your ADaM data and returns
   the table as JSON; the UI renders it styled to mimic the eventual
   RTF. The AI panel on the right is pre-loaded with the table data and
   shell spec — ask anything. Anomaly detection runs automatically and
   surfaces issues.
8. **Generate.** Batch-submit the selected shells. The UI shows live
   status. Failed jobs capture the full traceback and offer a Retry button.
9. **Outputs.** Browse generated RTFs and PNGs. Mark approved.
   "Download Package" emits a ZIP with all outputs + a manifest CSV.

---

## Adding a new table type

Add the implementation in the tlf library, not here:

1. In `crinetics-tlf-automation/shells/tables/` or `shells/figures/`,
   add a YAML file for the new output with an `id`, `column_layout`,
   `row_schema`, `footnotes`, `conditionality`, and `optional_flag`
   (if optional). Add the relative path to `shell_files:` in
   `crinetics-tlf-automation/shells/registry.yaml`.
2. In `crinetics-tlf-automation/src/tlf/tables/`, add a `generate(cfg,
   registry, **kwargs) -> Path` function that builds a `TableSpec` and
   calls `render_table`.
3. In `crinetics-tlf-studio/backend/services/generation_service.py`,
   add the shell id → function mapping in `_dispatchers()`.

The new shell now appears in the Select TFLs screen automatically, with
the correct conditionality and grouping.

---

## API surface

All endpoints are JSON unless noted.

| Method | Path | Purpose |
|--------|------|---------|
| GET    | /api/studies | List studies |
| POST   | /api/studies | Create a study |
| GET    | /api/studies/{id} | Full study detail |
| PUT    | /api/studies/{id} | Update study config |
| DELETE | /api/studies/{id} | Delete a study |
| POST   | /api/studies/{id}/upload | Multipart upload ADaM files |
| GET    | /api/studies/{id}/shells | Shell registry resolved against this study |
| PUT    | /api/studies/{id}/shells | Save shell selections |
| POST   | /api/studies/{id}/preview/{table_id} | Run aggregation, return JSON |
| POST   | /api/studies/{id}/jobs | Submit generation job(s) |
| GET    | /api/studies/{id}/jobs | List jobs |
| GET    | /api/studies/{id}/jobs/{job_id} | Job status |
| DELETE | /api/studies/{id}/jobs/{job_id} | Cancel job |
| GET    | /api/studies/{id}/outputs | List generated files |
| GET    | /api/studies/{id}/outputs/{output_id}/download | RTF download |
| POST   | /api/studies/{id}/outputs/{output_id}/status | Approve / reset |
| POST   | /api/studies/{id}/outputs/package | ZIP all outputs + manifest |
| POST   | /api/ai/sap | SAP PDF → structured config JSON |
| POST   | /api/ai/shells | Natural language → shell selection diff |
| POST   | /api/ai/chat | Streaming chat scoped to a table |
| POST   | /api/ai/anomalies | Rule-based + AI anomaly scan |

---

## Audit trail

For each generated output (`studies/{id}/outputs/<file>`) we write a
companion `studies/{id}/audit/<file_stem>.json` with:

- ADaM data extract date used
- Shell registry version
- Study config version
- Submitter (Celery task triggered_by)
- Approval status + approver + approval timestamp

`POST /api/studies/{id}/outputs/{output_id}/status` mutates the audit
record. The "Download Package" route includes a manifest.csv of every
file plus its approval status.

---

## Tests

```bash
cd backend
uv run pytest                # 30 tests, all green
```

Tests cover study CRUD, ADaM metadata extraction, shell registry +
conditionality resolution, the full generation pipeline (real
CDISCPILOT01 data when the sibling automation project is present), and
AI services with a mocked Anthropic client.

---

## Known limitations

- **Filesystem storage; no multi-user conflict resolution.** Two
  programmers editing the same study at once is undefined behaviour. A
  database layer is the natural next step.
- **AI SAP extraction must be reviewed.** The wizard never auto-applies
  AI output — every field stays editable and shows the source excerpt.
- **No ECG tables tested with real data.** The CDISCPILOT01 sample has
  no ADEG domain; the ECG generators produce a placeholder shell noting
  the absence. Drop an ADEG parquet in the study's `data/` directory to
  exercise them.
- **AI cost.** SAP extraction and anomaly detection each make a single
  Claude call per invocation. Cache or batch them if you're scanning
  many tables per session.
