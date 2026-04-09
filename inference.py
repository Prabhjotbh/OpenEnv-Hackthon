import os
import re
import json
import asyncio
import websockets
from openai import OpenAI

# --- Configuration ---

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "meta-llama/Llama-3.1-8B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "wss://prabhjot27-procure-env.hf.space/ws")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

TASKS     = ["task1_easy", "task2_medium", "task3_hard"]
MAX_STEPS = 30  # safety cap -- env enforces its own per-task limits

SYSTEM_PROMPT = """You are a procurement engineer evaluating industrial suppliers in India.
All prices are in Indian Rupees (INR, ₹).

AVAILABLE ACTIONS -- output exactly one valid JSON object per turn, nothing else:
{"action": "query",       "supplier_id": <int>, "field": "<lead_time|moq|reliability>"}
{"action": "request_doc", "supplier_id": <int>, "doc_type": "<quality_report|certifications|financial_stability>"}
{"action": "offer",       "supplier_id": <int>, "price": <float>, "quantity": <int>}
{"action": "accept",      "supplier_id": <int>}
{"action": "reject",      "supplier_id": <int>}

DECISION RULES (follow in priority order):
1. When required_certs is non-empty: request_doc(certifications) for every serious candidate
   BEFORE accepting. A missing cert zeroes out 30% of your score.
2. Always request_doc(quality_report) before accepting. Quality below 0.60 = reject.
3. Check reliability before committing. Reliability below 0.80 is a deception risk signal.
4. Negotiate: make offers 15-25% below quoted_price. Flexible suppliers accept; firm ones counter.
5. Budget constraint: (negotiated_price * quantity) must be <= rfq.budget.
6. Reject suppliers with missing required certs or quality < 0.60 early to conserve steps.
7. Focus on 2-3 promising suppliers. Do not check every supplier exhaustively.

OUTPUT: one JSON action object only. No markdown, no explanation, no extra text."""


# --- Observation formatting ---

def format_initial_observation(obs: dict) -> str:
    """
    Format the reset observation into a structured prompt for the first LLM turn.

    The raw JSON observation is passed on subsequent turns (via conversation history),
    but the first message benefits from a more readable layout that highlights the
    key constraints the agent needs to act on.
    """
    rfq = obs["rfq"]
    suppliers = obs.get("suppliers", [])

    sup_lines = "\n".join(
        f"  [{s['id']}] {s['name']} -- quoted ₹{s['quoted_price']:,.0f}/unit, status: {s['status']}"
        for s in suppliers
    )

    certs_note = ""
    if rfq.get("required_certs"):
        certs_note = (
            f"\nCOMPLIANCE: {', '.join(rfq['required_certs'])} required. "
            f"Verify certifications before accepting any supplier."
        )

    per_unit_budget = rfq["budget"] / rfq["quantity"] if rfq["quantity"] else 0

    return (
        f"New procurement task: {rfq['item']}\n"
        f"Quantity: {rfq['quantity']} units | Budget: ₹{rfq['budget']:,.0f} "
        f"(≤ ₹{per_unit_budget:,.0f}/unit) | Deadline: {rfq.get('deadline_days', 'TBD')} days"
        f"{certs_note}\n\n"
        f"Suppliers ({len(suppliers)} available):\n{sup_lines}\n\n"
        f"Steps available: {obs.get('steps_remaining', '?')}. "
        f"Gather information, negotiate, then accept the best compliant supplier."
    )


# --- Logging helpers ---

def log_end(success: bool, steps: int, score: float, rewards: list) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    success_str = str(success).lower()
    print(
        f"[END] success={success_str} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# --- Action extraction ---

def extract_action(text: str) -> dict:
    """
    Parse a JSON action object from LLM output.

    The LLM sometimes wraps the JSON in markdown fences or adds explanation text.
    Four extraction strategies in priority order:
      1. Direct parse -- clean JSON output
      2. Strip markdown fences -- ```json ... ```
      3. Regex first flat object -- first {...} without nested braces
      4. Regex greedy match -- widest {...} in the string
    Falls back to a no-op query if all strategies fail.
    """
    text = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences
    cleaned = text
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Strategy 3: first flat JSON object (no nested braces)
    match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 4: greedy match (handles escaped quotes inside values)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    print(f"[DEBUG] Could not parse action from LLM output: {text[:120]}", flush=True)
    return {"action": "query", "supplier_id": 1, "field": "lead_time"}


def call_llm(conversation_history: list[dict]) -> str:
    """
    Call the LLM with the full conversation history.

    Conversation history grows across the episode so the model can reference
    earlier decisions -- cert checks from step 3 should inform the accept
    decision at step 10.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversation_history)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=200,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


# --- Episode runner ---

async def run_task(task_id: str) -> dict:
    """
    Run one full procurement episode for the given task.

    Maintains conversation history across steps so the LLM agent can reason
    across turns. The [END] log line is emitted unconditionally via finally --
    even if the WebSocket drops or the LLM throws.
    """
    steps_taken  = 0
    all_rewards: list[float] = []
    final_score  = 0.0
    success      = False

    print(f"[START] task={task_id} env=procure_env model={MODEL_NAME}", flush=True)

    try:
        async with websockets.connect(ENV_BASE_URL) as ws:
            # Reset and format the initial observation for the first LLM turn
            await ws.send(json.dumps({"type": "reset", "task_id": task_id}))
            raw_obs = await ws.recv()
            obs = json.loads(raw_obs)

            conversation_history: list[dict] = [
                {"role": "user", "content": format_initial_observation(obs)}
            ]

            for step in range(1, MAX_STEPS + 1):
                if obs.get("done", False):
                    break

                try:
                    raw_response = call_llm(conversation_history)
                    action = extract_action(raw_response)
                except Exception as e:
                    print(f"[DEBUG] LLM call failed at step {step}: {e}", flush=True)
                    action = {"action": "query", "supplier_id": 1, "field": "reliability"}
                    raw_response = json.dumps(action)

                await ws.send(json.dumps({"type": "step", "action": action}))
                raw_obs = await ws.recv()
                obs = json.loads(raw_obs)

                reward = float(obs.get("reward", 0.0))
                done   = obs.get("done", False)
                all_rewards.append(reward)
                steps_taken = step

                action_str = json.dumps(action)
                print(
                    f"[STEP] step={step} action={action_str} "
                    f"reward={reward:.2f} done={str(done).lower()} error=null",
                    flush=True,
                )

                # Append both sides to history so the next turn has full context
                conversation_history.append({"role": "assistant", "content": raw_response})
                conversation_history.append({"role": "user", "content": obs.get("message", "")})

                if done:
                    break

            final_score = min(max(float(obs.get("cumulative_reward", 0.0)), 0.001), 0.999)
            success = final_score >= 0.4

    except Exception as e:
        print(f"[DEBUG] Episode error in {task_id}: {e}", flush=True)

    finally:
        log_end(success=success, steps=steps_taken, score=final_score, rewards=all_rewards)

    return {"task": task_id, "score": final_score, "success": success}


async def main():
    for task_id in TASKS:
        await run_task(task_id)
        print()  # blank line between task logs


if __name__ == "__main__":
    asyncio.run(main())
