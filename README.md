# Sentinel-Chain

Sentinel-Chain is an AI-powered log intelligence platform that ingests logs from edge
agents, verifies tamper resistance via a per-VM hash chain, runs LLM-based threat
analysis on each verified batch, and exposes results through a natural-language query
interface and an operator dashboard. It is a 5-person university capstone project,
targeting an MVP demo on 2 May 2026.

## Architecture

The system is split into three layers:

1. **Agents (M3).** Edge collectors read host logs, batch them, hash each batch into a
   chain, and POST to the backend. A log simulator and a tamper script exist for demo
   and testing.
2. **Backend (M2).** A FastAPI service authenticates requests by `X-API-Key`, stores
   log batches and AI threat reports in SQL, embeds log content into ChromaDB, runs
   Gemini analysis on each verified batch, and exposes the contract endpoints under
   `/ingest`, `/upload`, `/batches`, `/reports`, `/integrity`, `/query`, and `/health`.
3. **Dashboard (M4).** A Streamlit multi-page app consumes the backend API to show
   overview metrics, AI threat reports with filters, source/VM activity, per-VM
   integrity status, an NLP chat with citations, and PDF/CSV export.

The AI core (M1) provides the embedding + retrieval + Gemini analysis pipeline used by
the backend's `/ingest` and `/query` paths.

## Tech stack

- **API:** FastAPI, Uvicorn, Pydantic
- **Storage:** SQLAlchemy (async) over PostgreSQL or SQLite, ChromaDB for embeddings
- **AI:** LangChain, Google Gemini (`gemini-2.5-flash` by default), HuggingFace
  `all-MiniLM-L6-v2` embeddings
- **Dashboard:** Streamlit, fpdf2, pandas, requests
- **Tests:** pytest, pytest-asyncio, FastAPI TestClient

## Quick start: local development

```bash
git clone <repo-url> Sentinel-Chain
cd Sentinel-Chain

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set at minimum:
#   API_KEY=<choose-a-shared-secret>
#   GOOGLE_API_KEY=<your-gemini-api-key>
#   GEMINI_MODEL=gemini-2.5-flash
#   DATABASE_URL=sqlite+aiosqlite:///./sentinel_chain.db   # or a real Postgres URL
```

Run the backend:

```bash
uvicorn backend.main:app --reload
```

In a second terminal, run the dashboard:

```bash
streamlit run app.py
```

The dashboard's sidebar accepts the backend URL and API key at runtime. Alternatively,
set `SENTINEL_API_URL`, `SENTINEL_API_KEY`, `SENTINEL_DATA_SOURCE`, and
`SENTINEL_UI_THEME` in `.env`.

## Live demo

The demo backend runs on VM3 (M5) at `http://138.68.93.66:8000`. The dashboard's
default `Live` mode points there. Health: `GET /health` should return
`{"status":"ok"}`. The demo API key is shared in the team channel; it does not live
in this repo.

## Running tests

From the repo root with the venv active:

```bash
pytest
```

This runs the suite under `backend/tests/`: 29 tests covering health, auth, the
integrity hash engine, `/ingest`, `/upload`, `/query`, `/reports`, `/batches`, and
`/integrity`. Network access is not required. The Gemini and embedding calls are
mocked in `backend/tests/conftest.py`, and the database is in-memory SQLite reset
between tests.

## API documentation

The full request and response contract for every endpoint lives in `API_CONTRACT.md`
(currently v4). With the backend running, FastAPI also serves an interactive OpenAPI
UI at `http://localhost:8000/docs` and a raw schema at `/openapi.json`.

## Team and workstream structure

| Workstream | Scope |
|---|---|
| M1: AI core | `analyze.py`, `chat.py`, root-level `ingest.py`. Embedding, retrieval, Gemini structured threat-report schema, NLP query pipeline. |
| M2: Backend | `backend/`. FastAPI routes, async SQLAlchemy models, hash-chain integrity engine, AI orchestration on `/ingest` and `/upload`. |
| M3: Agents | `agent/`. Edge agent, log simulator, tamper script targeting the live deployment. |
| M4: Frontend | `app.py`, `pages/`, `frontend/`. Streamlit dashboard, mock-data fixtures, PDF/CSV exports. |
| M5: Infra | VM3 hosting, PostgreSQL provisioning, backend deployment at `138.68.93.66:8000`. |

## Project status

MVP target: 2 May 2026. As of late April 2026, the backend (M2) endpoints are
implemented and tested, the AI analysis and NLP query pipeline is functional, the
dashboard (M4) is merged and pointed at the live backend, and VM3 is deployed. Final
integration testing and tamper detection demo are pending. The seven committed MVP
user stories (US01-US07) plus US08 (PDF/CSV export) are wired end-to-end.
