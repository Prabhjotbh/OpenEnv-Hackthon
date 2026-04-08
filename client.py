"""
ProcureEnv Python Client

Provides both HTTP (stateless) and WebSocket (stateful) interfaces to the
ProcureEnv server.

Usage:
    # HTTP (stateless, one-shot per step):
    client = ProcureEnvHTTPClient(base_url="http://localhost:8000")
    obs = client.reset("task1_easy")
    obs = client.step({"action": "query", "supplier_id": 1, "field": "lead_time"})

    # WebSocket (stateful, multi-step session):
    async with ProcureEnvWSClient(ws_url="ws://localhost:8000/ws") as client:
        obs = await client.reset("task1_easy")
        obs = await client.step({"action": "query", "supplier_id": 1, "field": "lead_time"})
"""

import json
import asyncio
from typing import Optional

import requests
import websockets


class ProcureEnvHTTPClient:
    """Stateless HTTP client. Each step call resets the environment."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict:
        r = requests.get(f"{self.base_url}/health")
        r.raise_for_status()
        return r.json()

    def reset(self, task_id: str = "task1_easy") -> dict:
        r = requests.post(f"{self.base_url}/reset", params={"task_id": task_id})
        r.raise_for_status()
        return r.json()

    def step(self, action: dict, task_id: str = "task1_easy") -> dict:
        r = requests.post(
            f"{self.base_url}/step",
            params={"task_id": task_id},
            json=action,
        )
        r.raise_for_status()
        return r.json()

    def state(self, task_id: str = "task1_easy") -> dict:
        r = requests.get(f"{self.base_url}/state", params={"task_id": task_id})
        r.raise_for_status()
        return r.json()


class ProcureEnvWSClient:
    """
    Stateful WebSocket client. Maintains session across multiple steps.

    Use as an async context manager:
        async with ProcureEnvWSClient("ws://localhost:8000/ws") as client:
            obs = await client.reset("task1_easy")
            obs = await client.step({...})
    """

    def __init__(self, ws_url: str = "ws://localhost:8000/ws"):
        self.ws_url = ws_url
        self._ws = None

    async def __aenter__(self):
        self._ws = await websockets.connect(self.ws_url)
        return self

    async def __aexit__(self, *args):
        if self._ws:
            await self._ws.close()

    async def reset(self, task_id: str = "task1_easy") -> dict:
        await self._ws.send(json.dumps({"type": "reset", "task_id": task_id}))
        raw = await self._ws.recv()
        return json.loads(raw)

    async def step(self, action: dict) -> dict:
        await self._ws.send(json.dumps({"type": "step", "action": action}))
        raw = await self._ws.recv()
        return json.loads(raw)

    async def get_state(self) -> dict:
        await self._ws.send(json.dumps({"type": "state"}))
        raw = await self._ws.recv()
        return json.loads(raw)


# --- Quick test ---

async def _demo():
    async with ProcureEnvWSClient("ws://localhost:8000/ws") as client:
        obs = await client.reset("task1_easy")
        print("Reset:", obs["message"])

        obs = await client.step({"action": "query", "supplier_id": 1, "field": "lead_time"})
        print("Step:", obs["message"], "| reward:", obs["reward"])

        obs = await client.step({"action": "request_doc", "supplier_id": 1, "doc_type": "quality_report"})
        print("Step:", obs["message"], "| reward:", obs["reward"])

        obs = await client.step({"action": "offer", "supplier_id": 1, "price": 1100.0, "quantity": 50})
        print("Step:", obs["message"], "| reward:", obs["reward"])

        obs = await client.step({"action": "accept", "supplier_id": 1})
        print("Final:", obs["message"], "| cumulative_reward:", obs["cumulative_reward"])


if __name__ == "__main__":
    asyncio.run(_demo())
