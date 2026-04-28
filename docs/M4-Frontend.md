# M4 Frontend Dashboard

Streamlit entry point:

```bash
source .venv/bin/activate
streamlit run app.py
```

The dashboard now defaults to the live VM3 backend. Use the sidebar to confirm:

- `Theme`: `Dark` or `Light`
- `Data source`: `Live`
- `FastAPI URL`: `http://138.68.93.66:8000`
- `API key`: the same value as backend `API_KEY`.

For local testing, you can also launch with environment variables:

```bash
SENTINEL_DATA_SOURCE=Live \
SENTINEL_API_URL=http://138.68.93.66:8000 \
SENTINEL_API_KEY=Sentinel2026 \
SENTINEL_UI_THEME=Dark \
.venv/bin/streamlit run app.py
```

If protected pages show `401`, the dashboard is reaching VM3 but the backend API key does not match the value you entered.

Implemented M4 scope:

- Overview page with stat cards, latest report, source VM status, activity feed, and charts.
- NLP Chat page with source/log filters, example prompts, conversation history, citations, and upload UI.
- Reports page with filters, paginated report cards, evidence expanders, CSV export, and fpdf2 PDF export.
- Sources page with VM cards, last-seen state, batch count, and log-volume chart.
- Integrity page with verified/tampered banner, per-VM chain details, hash detail, CSV export, and PDF export.
- Export page for downloading report and integrity artifacts from one place.
- Global red alert bar on every page when any critical report or tampered chain exists.
