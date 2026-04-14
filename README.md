# Moyer's Estimate Parser

Insurance repair estimate PDF → Moyer's work-order Excel workbook.  
Upload any Xactimate, Symbility, or carrier-format PDF. AI extracts every line item and outputs a formatted `.xlsx` ready for work-order pricing.

An **LP First Capital** internal tool for Moyer's Services Group.

---

## How it works

1. Upload a PDF estimate (up to 150 pages, 100 MB)
2. PyMuPDF rasterizes each page to PNG at 150 DPI
3. Pages are sent to Claude Vision API in batches of 8
4. AI extracts every line item with section, trade, qty, pricing, and O&P
5. openpyxl builds the exact Moyer's Excel template
6. Download the `.xlsx` — WO% column is yellow, ready to fill in

---

## Local development

### Prerequisites
- Python 3.12+
- Node 20+

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY and APP_PASSWORD

python app.py
```

Backend runs at `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and proxies `/api/*` to Flask.

---

## Railway deployment

1. Push this repo to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Set environment variables in Railway dashboard:
   - `ANTHROPIC_API_KEY` — your Anthropic API key
   - `APP_PASSWORD` — shared password for the Moyer's team
   - `SECRET_KEY` — random 32-char hex string
   - `ALLOWED_ORIGINS` — your Railway app URL (e.g. `https://moyers.up.railway.app`)
4. Railway auto-detects the Dockerfile and deploys

No database needed. No migrations. Jobs are processed in-memory.

---

## Excel output format

| Column | Source |
|--------|--------|
| # | Sequential line number |
| Section / Room | Pulled from PDF |
| Trade | AI-assigned (17 categories) |
| Description | Pulled from PDF |
| Qty / Unit / Unit Price | Pulled from PDF |
| Tax / O&P / RCV / Depreciation / ACV | Pulled from PDF |
| Labor | Formula: RCV − O&P − Tax − Materials |
| Materials | Formula: Tax ÷ 6% |
| **WO%** | **Yellow — user fills in** |
| WO Labor Only | Formula: Labor × WO% |
| WO L&M | Formula: (Labor + Materials) × WO% |

Freeze panes at row 17. Section and Trade columns support Excel slicers.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | — | Anthropic API key |
| `APP_PASSWORD` | ✅ | — | Shared access password |
| `SECRET_KEY` | ✅ prod | dev key | Flask session secret |
| `ALLOWED_ORIGINS` | prod | `*` | CORS allowed origins |
| `MAX_UPLOAD_MB` | no | `100` | Max PDF size |
| `VISION_BATCH_SIZE` | no | `8` | Pages per Claude call |
| `CLAUDE_MODEL` | no | `claude-sonnet-4-20250514` | Claude model |
