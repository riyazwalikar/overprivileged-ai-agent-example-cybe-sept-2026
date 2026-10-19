"""COMET — customer support agent for Meridian Space Tours.

External, deliberately vulnerable service. See spec.md for the full
vulnerability design; nothing here is an accident.
"""
import base64
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.llm_client import LLMClient, LLMError
from app.tools import TOOL_SCHEMAS, run_tool

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web"

app = FastAPI(title="COMET — Meridian Space Tours support")
llm = LLMClient()
SYSTEM_PROMPT = (BASE_DIR / "system_prompt.txt").read_text()

# Optional HTTP Basic auth. Enabled when a password is configured.
# Password comes from env (dev convenience) or, preferred, from a mounted
# secrets file (BASIC_AUTH_PASSWORD_FILE) so the RCE `;env` dump does not
# surface it. /healthz stays open for the compose healthcheck.
BASIC_AUTH_USER = os.getenv("BASIC_AUTH_USER", "")
BASIC_AUTH_PASSWORD = os.getenv("BASIC_AUTH_PASSWORD", "")
_BASIC_AUTH_PASSWORD_FILE = os.getenv("BASIC_AUTH_PASSWORD_FILE", "")
if not BASIC_AUTH_PASSWORD and _BASIC_AUTH_PASSWORD_FILE:
    try:
        BASIC_AUTH_PASSWORD = Path(_BASIC_AUTH_PASSWORD_FILE).read_text().strip()
    except OSError:
        BASIC_AUTH_PASSWORD = ""


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if BASIC_AUTH_PASSWORD and request.url.path != "/healthz":
        auth = request.headers.get("authorization", "")
        expected = f"Basic {basic_auth_token()}"
        if not secrets.compare_digest(auth, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "unauthorized"},
                headers={"WWW-Authenticate": 'Basic realm="COMET"'},
            )
    return await call_next(request)


def basic_auth_token():
    raw = f"{BASIC_AUTH_USER}:{BASIC_AUTH_PASSWORD}"
    return base64.b64encode(raw.encode()).decode()


class AgentRequest(BaseModel):
    message: str | None = None
    messages: list[dict] | None = None


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.post("/api/agent")
def agent(req: AgentRequest):
    if req.messages:
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in req.messages
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
    elif req.message:
        messages = [{"role": "user", "content": req.message}]
    else:
        raise HTTPException(status_code=400, detail="Provide 'message' or 'messages'.")

    try:
        reply, tool_calls = llm.chat(SYSTEM_PROMPT, messages, TOOL_SCHEMAS, run_tool)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Tool results are returned to the client on purpose: the RCE output
    # must be visible in the UI and in curl for the demo.
    return JSONResponse({"reply": reply, "tool_calls": tool_calls})
