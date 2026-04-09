import os
import re
import json
import asyncio
import websockets
from openai import OpenAI

# --- Configuration ---

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "wss://prabhjot27-procure-env.hf.space/ws")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

TASKS = ["task1_easy", "task2_medium", "task3_hard"]
MAX_STEPS = 30  # safety cap (env has its own per-task limits)

SYSTEM_PROMPT = """You are a procurement engineer evaluating industrial suppliers to fulfill a purchase order.

AVAILABLE ACTIONS (output ONLY valid JSON, one action per turn):
{"action": "query", "supplier_id": <int>, "field": "<lead_time|moq|reliability>"}
{"action": "request_doc", "supplier_id": <int>, "doc_type": "<quality_report|certifications|financial_stability>"}
{"action": "offer", "supplier_id": <int>, "price": <float>, "quantity": <int>}
{"action": "accept", "supplier_id": <int>}
{"action": "reject", "supplier_id": <int>}

CRITICAL RULES (follow in order):
1. If required_certs is non-empty, ALWAYS request_doc(doc_type="certifications") for a supplier BEFORE accepting them. Missing certs = massive score penalty.
2. ALWAYS request_doc(doc_type="quality_report") for a supplier before accepting. Quality below 0.60 means reject them.
3. Check reliability for suppliers before committing. Reliability below 0.80 is a red flag for deception.
4. Negotiate aggressively: make offers 15-25% below quoted_price. Flexible suppliers will accept; firm ones will counter.
5. Stay within budget: total cost = price * quantity must be <= rfq.budget.
6. Reject suppliers missing required certifications or with poor quality early to save steps.
7. Focus on the 2-3 most promising suppliers. Do not waste steps checking all of them.

OUTPUT FORMAT: Respond with ONLY a valid JSON action object. No explanation, no markdown fences, no extra text.
"""


# --- Logging helpers ---

def log_end(success: bool, steps: int, score: float, rewards: list) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    success_str = str(success).lower()
    print(
        f"[END] success={success_str} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# --- Action extraction ---

def extract_action(text: str) -> dict:
    """Extract JSON action from LLM output, handling extra text."""
    text = text.strip()

    # Method 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Method 2: strip markdown fences
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

    # Method 3: regex -- first flat JSON object
    match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Method 4: greedy match (handles nested quotes)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: safe no-op action
    print(f"[DEBUG] Could not parse action from: {text[:100]}", flush=True)
    return {"action": "query", "supplier_id": 1, "field": "lead_time"}


def get_action(history: list[dict], observation: dict) -> dict:
    obs_text = json.dumps(observation, indent=2)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history:
        messages.append(h)
    messages.append({
        "role": "user",
        "content": f"Current observation:\n{obs_text}\n\nWhat is your next action?"
    })

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=200,
        temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()
    return extract_action(raw)


# --- Episode runner ---

async def run_task(task_id: str) -> dict:
    steps_taken = 0
    all_rewards = []
    final_score = 0.0
    success = False

    print(f"[START] task={task_id} env=procure_env model={MODEL_NAME}", flush=True)

    try:
        async with websockets.connect(ENV_BASE_URL) as ws:
            # Reset
            await ws.send(json.dumps({"type": "reset", "task_id": task_id}))
            raw_obs = await ws.recv()
            obs = json.loads(raw_obs)

            history = []

            for step in range(1, MAX_STEPS + 1):
                if obs.get("done", False):
                    break

                # Get action with fallback on parse errors
                try:
                    action = get_action(history, obs)
                except Exception as e:
                    print(f"[DEBUG] Action error: {e}", flush=True)
                    action = {"action": "query", "supplier_id": 1, "field": "reliability"}

                action_str = json.dumps(action)

                await ws.send(json.dumps({"type": "step", "action": action}))
                raw_obs = await ws.recv()
                obs = json.loads(raw_obs)

                reward = float(obs.get("reward", 0.0))
                done = obs.get("done", False)
                all_rewards.append(reward)
                steps_taken = step

                print(
                    f"[STEP] step={step} action={action_str} "
                    f"reward={reward:.2f} done={str(done).lower()} error=null",
                    flush=True,
                )

                history.append({"role": "assistant", "content": action_str})
                history.append({"role": "user", "content": obs.get("message", "")})

                if done:
                    break

            final_score = min(max(float(obs.get("cumulative_reward", 0.0)), 0.001), 0.999)
            success = final_score >= 0.4

    except Exception as e:
        print(f"[DEBUG] Episode error: {e}", flush=True)

    finally:
        log_end(success=success, steps=steps_taken, score=final_score, rewards=all_rewards)

    return {"score": final_score, "success": success}


async def main():
    for task_id in TASKS:
        await run_task(task_id)
        print()


if __name__ == "__main__":
    asyncio.run(main())
