---
title: ProcureEnv
emoji: "🚀"
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ProcureEnv

An OpenEnv-compliant reinforcement learning environment simulating industrial B2B procurement negotiations.

An agent acts as a procurement engineer: querying hidden supplier attributes, negotiating prices, verifying compliance certifications, and avoiding adversarial counterparties to fulfill a purchase requirement under budget and time constraints.

---

## Why ProcureEnv

Procurement engineers in industrial B2B contexts spend 4-8 hours evaluating
suppliers per purchase order -- querying specs, verifying certifications,
negotiating prices, and managing adversarial counterparties. Wrong supplier
selection causes 15-20% project cost overruns in manufacturing.

ProcureEnv is the first RL environment that models this decision process end-to-end,
enabling training and evaluation of agents that can assist or automate industrial
procurement. The environment captures information asymmetry (hidden attributes),
adversarial dynamics (deceptive supplier behavior), regulatory constraints
(mandatory certifications), and multi-objective optimization (cost vs quality vs compliance)
-- all present in real procurement workflows.

---

## Overview

ProcureEnv tests an agent's ability to:

- **Gather information under uncertainty** — supplier quality, reliability, and certifications are hidden until queried
- **Negotiate strategically** — prices are negotiable; suppliers have different behaviors (flexible, firm, deceptive)
- **Enforce compliance** — some tasks require specific certifications (ATEX, CE, ISO9001); accepting a non-compliant supplier incurs a score penalty
- **Manage step budget** — each episode has a fixed number of steps; wasting steps on redundant queries reduces effective decision space

Three tasks span easy (pure price negotiation) to hard (deceptive supplier, dual certification requirement, tight budget).

---

## Action Space

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `query` | `supplier_id`, `field` | Reveal a hidden field: `lead_time`, `moq`, or `reliability` |
| `request_doc` | `supplier_id`, `doc_type` | Request a document: `quality_report`, `certifications`, or `financial_stability` |
| `offer` | `supplier_id`, `price`, `quantity` | Submit a price offer to a supplier |
| `accept` | `supplier_id` | Finalize deal with supplier — ends episode |
| `reject` | `supplier_id` | Remove supplier from consideration |

---

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `rfq` | dict | Purchase requirement: item, quantity, budget, deadline_days, required_certs |
| `suppliers` | list | Visible supplier info: id, name, quoted_price, item_category, status |
| `revealed_info` | dict | Per-supplier map of fields revealed so far |
| `current_best_offers` | dict | Current negotiated price per supplier |
| `step_count` | int | Steps used so far |
| `steps_remaining` | int | Steps left before timeout |
| `done` | bool | Whether the episode has ended |
| `reward` | float | Reward from the last action |
| `cumulative_reward` | float | Total reward accumulated this episode |
| `accepted_supplier_id` | int or null | Supplier ID if a deal was finalized |
| `message` | str | Human-readable summary of what just happened |

---

## Tasks

### task1_easy
- **Difficulty:** Easy
- **Item:** Industrial Conveyor Belt Unit (qty: 50, budget: $75,000)
- **Suppliers:** 3 (all flexible or firm)
- **Compliance:** None required
- **Grading:** Weighted entirely on cost efficiency and due diligence

### task2_medium
- **Difficulty:** Medium
- **Item:** Pressure Relief Valve (qty: 200, budget: $300,000)
- **Suppliers:** 5 — one has a hidden quality score of 0.48 and no ATEX cert
- **Compliance:** ATEX required
- **Grading:** Certification compliance is 30% of score; quality check discovery rewarded

### task3_hard
- **Difficulty:** Hard
- **Item:** Hydraulic Pump System (qty: 30, budget: $180,000)
- **Suppliers:** 6 — one deceptive (revises price +20% on accept), two missing CE cert
- **Compliance:** CE + ISO9001 both required
- **Grading:** Deception penalty (40% reduction); tight budget makes cost efficiency critical

---

## Reward Function

### Per-step rewards
| Event | Reward |
|-------|--------|
| New field revealed via `query` | +0.01 |
| New document revealed via `request_doc` | +0.03 |
| Discovering quality issue (score < 0.60) | +0.05 |
| Discovering missing required cert | +0.05 |
| Successful price negotiation (flexible supplier) | proportional to improvement |
| Deceptive supplier accepts offer in negotiation | +0.04 |
| Invalid action / querying rejected supplier | -0.01 to -0.02 |

### Terminal reward (on accept)
Score = cost_efficiency (40%) + cert_compliance (30%) + quality_check (20%) + due_diligence (10%)

- **Cost efficiency:** How close the final price is to the theoretical best-possible among valid suppliers
- **Cert compliance:** Fraction of required certs held by accepted supplier
- **Quality check:** Full credit (0.20) if quality_report was requested and score >= 0.60
- **Due diligence:** Credit for checking lead_time, moq, reliability, certifications (up to 0.10)
- **Deception penalty:** All components multiplied by 0.4 if agent was deceived

All suppliers rejected: -0.5 terminal penalty. Timeout: 0 terminal reward.

---

## Setup & Usage

### Local development

```bash
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

### Test endpoints

```bash
# Health check
curl http://localhost:8000/health

# Reset environment
curl -X POST "http://localhost:8000/reset?task_id=task1_easy"

# Single step (stateless)
curl -X POST "http://localhost:8000/step?task_id=task1_easy" \
  -H "Content-Type: application/json" \
  -d '{"action": "query", "supplier_id": 1, "field": "lead_time"}'
```

### Docker

```bash
docker build -t procure-env .
docker run -p 7860:7860 procure-env
```

### Python client example

```python
import asyncio
from client import ProcureEnvWSClient

async def run():
    async with ProcureEnvWSClient("ws://localhost:8000/ws") as client:
        obs = await client.reset("task1_easy")
        print(obs["message"])

        obs = await client.step({"action": "query", "supplier_id": 1, "field": "lead_time"})
        obs = await client.step({"action": "request_doc", "supplier_id": 1, "doc_type": "quality_report"})
        obs = await client.step({"action": "offer", "supplier_id": 1, "price": 1050.0, "quantity": 50})
        obs = await client.step({"action": "accept", "supplier_id": 1})
        print(f"Final score: {obs['cumulative_reward']:.3f}")

asyncio.run(run())
```

### Baseline inference (LLM agent)

```bash
export HF_TOKEN=hf_...
export ENV_BASE_URL=wss://prabhjot27-procure-env.hf.space/ws
export MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
python inference.py
```

---

## Baseline Scores

Scores from running `inference.py` with `meta-llama/Llama-3.1-8B-Instruct` via HuggingFace Inference API:

| Task | Cumulative Reward | Steps Used | Success |
|------|-------------------|------------|---------|
| task1_easy | 0.83 | 6 | Yes |
| task2_medium | 0.84 | 6 | Yes |
| task3_hard | 0.58 | 11 | Yes |

*Scores from Llama-3.1-8B-Instruct via HuggingFace Inference API. Will update after final run.*
