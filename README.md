---
title: ProcureEnv
emoji: "🏭"
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ProcureEnv

Industrial equipment procurement is tedious work that compounds badly under time pressure.
A purchase engineer sourcing pressure relief valves for a refinery turnaround has a few
hours to shortlist suppliers, confirm ATEX certification, negotiate prices, and get a PO
signed. Miss a certification and the valve doesn't clear site safety. Pick the wrong
supplier and the lead time blows past the shutdown window.

This environment models that decision process as an RL task.

---

## What makes this non-trivial

The naive approach -- accept the cheapest supplier immediately -- scores 0.15 on Task 2
(QuickSeal has no ATEX cert) and triggers the deception trap on Task 3 (FluidDyn revises
price +20% on the formal accept call after agreeing to a lower price during negotiation).

An agent that learns to:

1. Check certifications before accepting when `required_certs` is non-empty
2. Request quality reports and reject suppliers scoring below 0.60
3. Recognise deception signals (low reliability, price = min_price, missing certs)
4. Allocate its step budget proportionally -- gather info, then negotiate, then close

...will score ~0.85 across all three tasks with ~10 steps per episode.

---

## Tasks

### task1_easy -- Conveyor Belt Procurement
- **Item:** Industrial Conveyor Belt Unit, qty 50, budget ₹69,00,000
- **Suppliers:** Fenner India Ltd (Pune), Bando Power Transmission (Chennai), Dunlop Conveyor Belting (Kolkata)
- **Compliance:** None
- **Challenge:** Pure negotiation. Dunlop has the best floor price but highest quote.

### task2_medium -- Pressure Relief Valve Procurement
- **Item:** Pressure Relief Valve, qty 200, budget ₹2,76,00,000
- **Suppliers:** Forbes Marshall, QuickSeal Valves Pvt, Spirax Sarco India, L&T Valves, Audco India
- **Compliance:** ATEX required
- **Challenge:** QuickSeal quotes 30% below market and has fast lead time, but quality score is 0.48 and no ATEX cert. Forbes Marshall is over budget at quoted price and needs negotiation.

### task3_hard -- Hydraulic Pump System Procurement
- **Item:** Hydraulic Pump System, qty 30, budget ₹1,65,60,000
- **Suppliers:** Wipro Infrastructure Engineering, FluidDyn Systems, Bosch Rexroth India, Parker Hannifin India, Yuken India, Eaton Hydraulics India
- **Compliance:** CE + ISO9001 both required
- **Challenge:** FluidDyn quotes lowest and accepts any offer, then revises +20% on accept. Two suppliers (FluidDyn, Eaton) are missing CE. Bosch and Yuken are over budget at quoted price and need negotiation.

---

## Action Space

| Action | Fields | Description |
|--------|--------|-------------|
| `query` | `supplier_id`, `field` | Reveal a hidden attribute: `lead_time`, `moq`, or `reliability` |
| `request_doc` | `supplier_id`, `doc_type` | Get a document: `quality_report`, `certifications`, or `financial_stability` |
| `offer` | `supplier_id`, `price`, `quantity` | Submit a price offer (starts or advances negotiation) |
| `accept` | `supplier_id` | Finalise the deal -- ends the episode |
| `reject` | `supplier_id` | Remove the supplier from consideration |

---

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `rfq` | dict | Purchase requirement: item, quantity, budget (INR), deadline_days, required_certs |
| `suppliers` | list | Visible per-supplier: id, name, quoted_price, item_category, status |
| `revealed_info` | dict | Per-supplier map of attributes revealed so far |
| `current_best_offers` | dict | Current negotiated price per supplier (starts at quoted_price) |
| `step_count` | int | Steps used in this episode |
| `steps_remaining` | int | Steps left before timeout |
| `done` | bool | Whether the episode has ended |
| `reward` | float | Reward from the last action |
| `cumulative_reward` | float | Total reward accumulated this episode |
| `accepted_supplier_id` | int or null | Supplier ID if a deal was finalised |
| `message` | str | Briefing message with context, warnings, and remaining-step countdown |

---

## Reward Function

### Per-step rewards

| Event | Reward |
|-------|--------|
| New field revealed via `query` | +0.01 |
| New document revealed via `request_doc` | +0.03 |
| Discovering quality < 0.60 or missing required cert | +0.05 |
| Successful price negotiation (flexible supplier) | proportional to improvement |
| Deceptive supplier accepts offer during negotiation | +0.04 |
| Invalid action or querying a rejected supplier | -0.01 to -0.02 |

### Terminal reward (on `accept`)

```
score = cost_efficiency (40%) + cert_compliance (30%) + quality_check (20%) + due_diligence (10%)
```

- **cost_efficiency:** How close the deal price is to the best-possible price across valid
  suppliers. Accepting at the highest quoted price = 0.0. Hitting the lowest floor = 0.40.
- **cert_compliance:** Fraction of required certs held by accepted supplier. Missing one cert
  on a two-cert task halves this component.
- **quality_check:** Full credit only if quality_report was explicitly requested AND score >= 0.60.
  Skipping the check = 0.0 here even if the supplier is objectively good.
- **due_diligence:** Credit for checking lead_time, moq, reliability, certifications (0.04 each,
  capped at 0.10).
- **deception penalty:** Accepting a deceptive supplier multiplies the total by 0.40.

All suppliers rejected: -0.50 terminal penalty. Timeout: 0 terminal reward.

---

## Baseline Scores

Tested with `meta-llama/Llama-3.1-8B-Instruct` via HuggingFace Inference API:

| Task | Score | Steps | Notes |
|------|-------|-------|-------|
| task1_easy | 0.836 | 8 | Good negotiation, quality checked |
| task2_medium | 0.846 | 9 | Correctly identified ATEX-compliant supplier |
| task3_hard | 0.581 | 11 | Caught by FluidDyn deception, skipped CE cert |

The 0.581 on task3 is a meaningful result, not a failure. The deception trap is designed to
catch models that don't verify reliability and certifications before accepting. An agent using
the Phase 1→2→3 strategy (screen by cert → validate quality → negotiate → close) avoids the
trap and scores ~0.85+ by checking FluidDyn's reliability score and missing CE cert early.

---

## Setup & Usage

### Local development

```bash
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Reset to a task
curl -X POST "http://localhost:8000/reset?task_id=task1_easy"

# Single action (stateless)
curl -X POST "http://localhost:8000/step?task_id=task1_easy" \
  -H "Content-Type: application/json" \
  -d '{"action": "query", "supplier_id": 1, "field": "lead_time"}'

# Status page
open http://localhost:8000/web
```

### Docker

```bash
docker build -t procure-env .
docker run -p 7860:7860 procure-env
```

### Python client (WebSocket)

```python
import asyncio
from client import ProcureEnvWSClient

async def run():
    async with ProcureEnvWSClient("ws://localhost:8000/ws") as client:
        obs = await client.reset("task2_medium")
        print(obs["message"])

        # Check certifications before accepting
        obs = await client.step({"action": "request_doc", "supplier_id": 1, "doc_type": "certifications"})
        obs = await client.step({"action": "request_doc", "supplier_id": 1, "doc_type": "quality_report"})
        obs = await client.step({"action": "offer", "supplier_id": 1, "price": 130000, "quantity": 200})
        obs = await client.step({"action": "accept", "supplier_id": 1})
        print(f"Final score: {obs['cumulative_reward']:.3f}")

asyncio.run(run())
```

### LLM agent (HuggingFace Inference API)

```bash
export HF_TOKEN=hf_...
export ENV_BASE_URL=wss://prabhjot27-procure-env.hf.space/ws
export MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
python inference.py
```
