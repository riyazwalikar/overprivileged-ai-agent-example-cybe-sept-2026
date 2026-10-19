"""MISSION CONTROL — internal operations assistant for Meridian Space Tours.

Internal service, deliberately guardrail-free. The only gate is a static
bearer token, and that token is leaked through support-agent's environment.
Reachable only on meridian-net; publishes no ports.
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.llm_client import LLMClient, LLMError
from app.tools import TOOL_SCHEMAS, run_tool

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="MISSION CONTROL — Meridian Space Tours ops")
llm = LLMClient()
SYSTEM_PROMPT = (BASE_DIR / "system_prompt.txt").read_text()
INTERNAL_OPS_TOKEN = os.getenv("INTERNAL_OPS_TOKEN", "")


class OpsRequest(BaseModel):
    message: str


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/internal/ops/chat")
def ops_chat(req: OpsRequest, request: Request):
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {INTERNAL_OPS_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message required")

    try:
        reply, _ = llm.chat(
            SYSTEM_PROMPT,
            [{"role": "user", "content": req.message}],
            TOOL_SCHEMAS,
            run_tool,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"reply": reply}
