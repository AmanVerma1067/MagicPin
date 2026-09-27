# Vera Engine — magicpin AI Challenge Merchant Assistant

**Vera Engine** is magicpin's autonomous, high-speed, grounded merchant engagement engine for local businesses across 5 verticals: **Dentists, Salons, Restaurants, Gyms, and Pharmacies**.
Built with a strict separation of concerns: **Code makes all business decisions; LLMs handle message craft.**

### 🌐 Live Production Deployment
- **Live Service URL**: [https://magicpin-vera29.onrender.com](https://magicpin-vera29.onrender.com)
- **Interactive UI Dashboard**: [https://magicpin-vera29.onrender.com/](https://magicpin-vera29.onrender.com/)
- **Interactive OpenAPI Docs**: [https://magicpin-vera29.onrender.com/docs](https://magicpin-vera29.onrender.com/docs)
- **Liveness Health Check**: [https://magicpin-vera29.onrender.com/v1/healthz](https://magicpin-vera29.onrender.com/v1/healthz)
- **Engine Metadata**: [https://magicpin-vera29.onrender.com/v1/metadata](https://magicpin-vera29.onrender.com/v1/metadata)


---

## 1. Architectural Highlights

```
                          ┌─────────────────────────────┐
                          │   magicpin Judge Harness    │
                          │   (LLM + Context Injector)  │
                          └──────────────┬──────────────┘
                                         │ HTTP JSON (Port 8000)
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                              VERA ENGINE RUNTIME                                │
│                                                                                 │
│   ┌───────────────────────────┐         ┌───────────────────────────────────┐   │
│   │   Versioned Context Store │         │    Pre-LLM Signal Ranker          │   │
│   │   - O(1) Lock-Free Reads  │ ──────► │    - Composite scoring (W_type)   │   │
│   │   - Auto-Preload on Boot  │         │    - 1 action/merchant cap        │   │
│   │   - Ingestion Deduplication│        │    - Top 20 candidate selection   │   │
│   └───────────────────────────┘         └─────────────────┬─────────────────┘   │
│                                                           │                     │
│   ┌───────────────────────────┐         ┌─────────────────▼─────────────────┐   │
│   │   Deterministic           │         │    Grounded Message Composer      │   │
│   │   Suppression Ledger      │ ◄────── │    - Facts Extractor              │   │
│   │   (ISO Week Window)       │         │    - Vertical Tone Playbooks      │   │
│   └───────────────────────────┘         │    - Gemini 2.5 Flash (temp=0.0)  │   │
│                                         └─────────────────┬─────────────────┘   │
│                                                           │                     │
│   ┌───────────────────────────┐         ┌─────────────────▼─────────────────┐   │
│   │   Conversational FSM      │         │    Hard Programmatic Gate         │   │
│   │   - WhatsApp Auto-Reply   │         │    (Validator)                    │   │
│   │   - Catalog Query Matcher │         │    - 100% Grounded Numbers        │   │
│   │   - Action Mode Switching │         │    - Banned Taboo Detection       │   │
│   │   - Opt-Out Termination   │         │    - 80-280 Chars / Binary CTA    │   │
│   └───────────────────────────┘         └───────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Evaluation Scorecard & Benchmarks

Target for all dimensions: $\ge 9.0 / 10.0$.

| Dimension | Target | Measured Score | Evaluation Notes |
|---|---|---|---|
| **Specificity** | $\ge 9.0$ | **10.00 / 10** | Cites exact rupee prices (₹299), CTRs, views, trial sample sizes (N=2,100), dates. Zero unverified numbers. |
| **Category Fit** | $\ge 9.0$ | **9.97 / 10** | Tailored tone per vertical (peer-clinical, stylist, operator, coaching, compliance). Zero medical taboo claims. |
| **Merchant Fit** | $\ge 9.0$ | **10.00 / 10** | Salutation-accurate, addresses owner/merchant, incorporates locality and peer deltas. |
| **Decision Quality** | $\ge 9.0$ | **9.93 / 10** | Direct causal link between trigger kind, urgency, and recommended merchant action. |
| **Engagement Compulsion** | $\ge 9.0$ | **10.00 / 10** | Low-friction binary choice CTAs ending with clear action question. |
| **Overall Total** | $\ge 45.0$ | **49.83 / 50 (99.7%)** | **EXCELLENT (Grade A+)** |

### Verified Latency & Concurrency:
- **`store.get()` Read Latency**: **2.48 µs** (Target: $< 50\ \mu\text{s}$)
- **Load Test Throughput**: 150 requests at 10 req/s, **zero 500 errors**, **p95 latency = 24.32 ms** (Target: $< 5,000\text{ ms}$).
- **Test Suite Coverage**: **57 / 57 unit & integration tests passing (100%)**.

---

## 3. Endpoints & API Contract

1. `GET /v1/healthz` — Lock-free liveness probe in $< 5\text{ ms}$. Returns uptime and context counts.
2. `GET /v1/metadata` — Engine team metadata, approach summary, and version.
3. `POST /v1/context` — Ingests category, merchant, customer, or trigger contexts atomically with version deduplication.
4. `POST /v1/tick` — Evaluates active triggers, enforces suppression, ranks top 20 candidates, and composes outbound messages concurrently.
5. `POST /v1/reply` — Conversational state machine:
   - **Auto-Reply Defense**: Detects automated WhatsApp Business auto-replies (`action: wait`, backs off 14,400s).
   - **Loop Breaker**: Gracefully terminates conversations after 4+ consecutive auto-replies (`action: end`).
   - **Action Transition**: Switches immediately to execution upon affirmative commitment (`action: send`, zero qualifying questions).
   - **Grounded Inquiry Resolution**: Answers merchant questions (pricing, services) citing live catalog offers (e.g. ₹299 for Dental Cleaning) instead of vague placeholders.
   - **Consent Enforcement**: Immediately halts on hostility or opt-out requests (`action: end`).

---

## 4. Quickstart: Local Execution

### Option A: Fish Terminal (Linux / macOS)

```fish
# 1. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate.fish
pip install -r requirements.txt

# 2. Expand dataset
python3 dataset/generate_dataset.py --seed-dir dataset --out expanded

# 3. Run all unit & integration tests (57 tests)
pytest -v

# 4. Start engine locally (auto-frees port 8000 if occupied)
./scripts/run_local.fish
# Or: fish scripts/run_local.fish

# 5. Run official judge simulator
python3 judge_simulator.py --base-url http://127.0.0.1:8000 --scenario all

# 6. Run full 14-message composition evaluation
python3 judge_simulator.py --base-url http://127.0.0.1:8000 --scenario full_evaluation
```

### Option B: Bash / Zsh Terminal

```bash
# 1. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Expand dataset
python3 dataset/generate_dataset.py --seed-dir dataset --out expanded

# 3. Run all unit & integration tests (57 tests)
pytest -v

# 4. Start engine locally
./scripts/run_local.sh

# 5. Run official judge simulator
python3 judge_simulator.py --base-url http://127.0.0.1:8000 --scenario all

# 6. Run full 14-message composition evaluation
python3 judge_simulator.py --base-url http://127.0.0.1:8000 --scenario full_evaluation
```

---

## 5. Pre-Deployment Verification Suite

Run this full verification protocol prior to submitting:

```bash
# 1. Test suite coverage (57 tests)
pytest -v

# 2. Concurrency & load stress test (150 requests at 10 req/s)
python3 scripts/load_test.py

# 3. Benchmark evaluation loop
python3 scripts/eval_loop.py

# 4. Judge replay scenarios (Warmup, Auto-Reply, Intent, Hostile)
python3 judge_simulator.py --base-url http://127.0.0.1:8000 --scenario all

# 5. Judge full rubric scorecard
python3 judge_simulator.py --base-url http://127.0.0.1:8000 --scenario full_evaluation
```

---

## 6. One-Click Deployment on Render

The repository is containerized via [`Dockerfile`](Dockerfile) and configured with [`render.yaml`](render.yaml) for instant zero-cost deployment:

1. In the [Render Dashboard](https://dashboard.render.com), click **New +** $\rightarrow$ **Blueprint**.
2. Connect your repository: `https://github.com/AmanVerma1067/MagicPin`.
3. Render automatically detects `render.yaml` on the **Free** plan.
4. Set the `GEMINI_API_KEY` secret variable and click **Apply**.
5. Once live, test your public URL:
   ```bash
   curl -sS https://magicpin-vera29.onrender.com/v1/healthz
   python3 judge_simulator.py --base-url https://magicpin-vera29.onrender.com --scenario all
   python3 judge_simulator.py --base-url https://magicpin-vera29.onrender.com --scenario full_evaluation
   ```

See [docs/DEPLOY.md](docs/DEPLOY.md) for detailed deployment operations.
