# Vera Engine — Render Deployment & Operations Guide

## 1. Overview
The Vera Engine is containerized via Docker and orchestrated on Render using `render.yaml` Blueprint specification.

- **Service Name**: `magicpin-vera29`
- **Environment**: Docker (`python:3.11-slim`)
- **Region**: Oregon (`oregon`)
- **Health Check Path**: `/v1/healthz`
- **Instance Sizing**: Free tier (zero cost) or Starter
- **Concurrency**: Single worker (`--workers 1`) handling async I/O via `asyncio` and `uvloop`

---

## 2. One-Click Blueprint Deployment

1. **Connect GitHub Repository**:
   - Repository: `https://github.com/AmanVerma1067/MagicPin`
   - In Render Dashboard, click **New +** -> **Blueprint**.
   - Select `AmanVerma1067/MagicPin`. Render will automatically detect `render.yaml`.
2. **Environment Variables**:
   - `GEMINI_API_KEY`: Set your Google Gemini API key.
   - All other parameters (`GEMINI_MODEL`, `LLM_TIMEOUT_S`, `TICK_DEADLINE_S`, `REPLY_DEADLINE_S`, `COMPOSE_CONCURRENCY`, `TEAM_NAME`, `TEAM_MEMBERS`, `APP_VERSION`) are pre-configured in `render.yaml`.
3. **Deploy**:
   - Click **Apply**.
   - Render will build the container from `Dockerfile`, install dependencies, run health checks against `/v1/healthz`, and assign a public domain:
     `https://magicpin-vera29.onrender.com`

---

## 3. Remote Verification

Once deployed on Render, execute:

```bash
# 1. Health check
curl -sS https://magicpin-vera29.onrender.com/v1/healthz

# 2. Metadata check
curl -sS https://magicpin-vera29.onrender.com/v1/metadata

# 3. Remote Judge Simulator Execution
python3 judge_simulator.py --base-url https://magicpin-vera29.onrender.com --scenario all

# 4. Full Remote Evaluation (14 messages across 5 verticals)
python3 judge_simulator.py --base-url https://magicpin-vera29.onrender.com --scenario full_evaluation
```

