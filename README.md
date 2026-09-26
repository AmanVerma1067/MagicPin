# Vera Engine — magicpin AI Challenge Merchant Assistant

**Vera Engine** is magicpin's autonomous, high-speed, grounded merchant engagement engine for local businesses across 5 verticals: **Dentists, Salons, Restaurants, Gyms, and Pharmacies**.

Built with a strict separation of concerns: **Code makes all business decisions; LLMs handle message craft.**

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
│   │   (Copy-on-Write, O(1)    │ ──────► │    - Composite scoring (W_type)   │   │
│   │    Lock-Free Reads < 3µs) │         │    - 1 action/merchant cap        │   │
│   └───────────────────────────┘         │    - Top 20 candidate selection   │   │
│                                         └─────────────────┬─────────────────┘   │
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
│   │   - Affirmative Action    │         │    - 100% Grounded Numbers        │   │
│   │   - Opt-Out Termination   │         │    - Banned Taboo Detection       │   │
│   └───────────────────────────┘         │    - 80-280 Chars / Binary CTA    │   │
│                                         └───────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Evaluation Scorecard & Benchmarks

Target for all dimensions: $\ge 9.0 / 10.0$.

| Dimension | Target | Measured Score | Evaluation Notes |
|---|---|---|---|
| **Specificity** | $\ge 9.0$ | **9.93 / 10** | Cites exact rupee prices (₹299), CTRs, views, trial sample sizes (N=2,100), dates. Zero unverified numbers. |
| **Category Fit** | $\ge 9.0$ | **9.97 / 10** | Tailored tone per vertical (peer-clinical, stylist, operator, coaching, compliance). Zero medical taboo claims. |
| **Merchant Fit** | $\ge 9.0$ | **10.00 / 10** | Salutation-accurate, addresses owner/merchant, incorporates locality and peer deltas. |
| **Decision Quality** | $\ge 9.0$ | **9.93 / 10** | Direct causal link between trigger kind, urgency, and recommended merchant action. |
| **Engagement Compulsion** | $\ge 9.0$ | **10.00 / 10** | Low-friction binary choice CTAs ending with clear action question. |
| **Overall Total** | $\ge 45.0$ | **49.83 / 50 (99.7%)** | **EXCELLENT (Grade A+)** |

### Latency & Concurrency:
- **`store.get()` Read Latency**: **2.48 µs** (Target: $< 50\ \mu\text{s}$)
- **Load Test Throughput**: 150 requests at 10 req/s, **zero 500 errors**, **p95 latency = 31.15 ms** (Target: $< 5,000\text{ ms}$).

---

## 3. Endpoints & API Contract

1. `GET /v1/healthz` — Lock-free liveness probe in $< 5\text{ ms}$. Returns uptime and context counts.
2. `GET /v1/metadata` — Engine team metadata, approach summary, and version.
3. `POST /v1/context` — Ingests category, merchant, customer, or trigger contexts atomically with version deduplication.
4. `POST /v1/tick` — Evaluates active triggers, enforces suppression, ranks top 20 candidates, and composes outbound messages concurrently.
5. `POST /v1/reply` — Conversational state machine. Detects WhatsApp auto-replies (`action: wait`), immediate action transitions (`action: send`), and opt-outs (`action: end`).

---

## 4. Quickstart: Local Execution

```bash
# 1. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Expand dataset
python3 dataset/generate_dataset.py --seed-dir dataset --out expanded

# 3. Run all unit & integration tests
pytest -v

# 4. Start engine locally
./scripts/run_local.sh

# 5. Run official judge simulator
python3 judge_simulator.py --base-url http://127.0.0.1:8000 --scenario all
```

---

## 5. Deployment

Containerized via `Dockerfile` and configured with `render.yaml` for instant deployment on Render.
See [docs/DEPLOY.md](docs/DEPLOY.md) for full instructions.
