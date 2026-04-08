from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Query
from fastapi.responses import HTMLResponse
from typing import Optional
import json
import os

import uvicorn

from server.environment import ProcureEnvironment
from models import ProcureObservation

app = FastAPI(
    title="ProcureEnv",
    description="Industrial B2B Procurement RL Environment"
)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/reset")
async def reset(
    task_id: Optional[str] = Query(None),
    body: dict = Body(default={})
):
    tid = task_id or body.get("task_id", "task1_easy")
    env = ProcureEnvironment(task_id=tid)
    obs = env.reset()
    return obs.model_dump()


@app.post("/step")
def step(action: dict = Body(default={}), task_id: str = "task1_easy"):
    """Stateless HTTP step -- resets env each time. Use /ws for stateful sessions."""
    if "action" in action and isinstance(action.get("action"), dict):
        payload = action["action"]
        task_id = action.get("task_id", task_id)
    else:
        payload = action
    env = ProcureEnvironment(task_id=task_id)
    env.reset()
    obs = env.step(payload)
    return obs.model_dump()


@app.get("/state")
def state(task_id: str = "task1_easy"):
    env = ProcureEnvironment(task_id=task_id)
    env.reset()
    return env.state.model_dump()


@app.get("/web", response_class=HTMLResponse)
def web_ui():
    return """<!DOCTYPE html>
<html>
<head><title>ProcureEnv</title>
<style>
body{font-family:monospace;background:#0f0f0f;color:#e0e0e0;padding:2rem;max-width:800px;margin:auto}
h1{color:#4ade80}h2{color:#94a3b8;margin-top:2rem}
table{width:100%;border-collapse:collapse;margin:1rem 0}
td,th{border:1px solid #333;padding:0.5rem;text-align:left}
th{background:#1a1a1a;color:#4ade80}
.badge{background:#1a3a1a;color:#4ade80;padding:2px 8px;border-radius:4px;font-size:0.85em}
a{color:#4ade80}
</style>
</head>
<body>
<h1>ProcureEnv</h1>
<p>Industrial B2B Procurement Negotiation &mdash; OpenEnv RL Environment</p>
<p>An agent acts as a procurement engineer: querying hidden supplier attributes,
negotiating prices, verifying compliance certifications, and avoiding adversarial
counterparties to fulfill purchase requirements under budget constraints.</p>

<h2>Tasks</h2>
<table>
<tr><th>Task</th><th>Difficulty</th><th>Max Steps</th><th>Key Challenge</th></tr>
<tr><td>task1_easy</td><td><span class="badge">Easy</span></td><td>12</td><td>Price negotiation with 3 suppliers</td></tr>
<tr><td>task2_medium</td><td><span class="badge">Medium</span></td><td>18</td><td>ATEX cert required, hidden quality issue</td></tr>
<tr><td>task3_hard</td><td><span class="badge">Hard</span></td><td>25</td><td>Deceptive supplier, dual cert, tight budget</td></tr>
</table>

<h2>Endpoints</h2>
<table>
<tr><th>Endpoint</th><th>Method</th><th>Description</th></tr>
<tr><td>/ws</td><td>WebSocket</td><td>Persistent stateful session (recommended)</td></tr>
<tr><td>/reset</td><td>POST</td><td>Reset environment</td></tr>
<tr><td>/step</td><td>POST</td><td>Execute action (stateless)</td></tr>
<tr><td>/state</td><td>GET</td><td>Environment state</td></tr>
<tr><td>/health</td><td>GET</td><td>Health check</td></tr>
<tr><td>/docs</td><td>GET</td><td>OpenAPI documentation</td></tr>
</table>

<p><a href="/docs">View API docs</a> | <a href="/health">Health check</a></p>
</body>
</html>"""


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Stateful WebSocket session.
    Client sends: {"type": "reset", "task_id": "task1_easy"}
                  {"type": "step", "action": {...}}
    Server responds with observation JSON each time.
    """
    await websocket.accept()
    env: ProcureEnvironment | None = None

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "reset":
                task_id = msg.get("task_id", "task1_easy")
                env = ProcureEnvironment(task_id=task_id)
                obs = env.reset()
                await websocket.send_text(obs.model_dump_json())

            elif msg.get("type") == "step":
                if env is None:
                    await websocket.send_text(json.dumps({"error": "Call reset first"}))
                    continue
                action = msg.get("action", {})
                obs = env.step(action)
                await websocket.send_text(obs.model_dump_json())

            elif msg.get("type") == "state":
                if env is None:
                    await websocket.send_text(json.dumps({"error": "Call reset first"}))
                    continue
                await websocket.send_text(env.state.model_dump_json())

            else:
                await websocket.send_text(json.dumps({"error": f"Unknown type: {msg.get('type')}"}))

    except WebSocketDisconnect:
        pass


def main():
    uvicorn.run(
        "server.app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "7860")),
    )


if __name__ == "__main__":
    main()
