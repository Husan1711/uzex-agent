from __future__ import annotations

import os
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import agent, db, llm
from .resolve import resolve

ROOT = os.path.join(os.path.dirname(__file__), "..", "static")
app = FastAPI(title="UZEX reyestr agenti")
_slots = threading.Semaphore(int(os.environ.get("MAX_PARALLEL", "4")))


class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[dict] = []


@app.on_event("startup")
def warm() -> None:
    resolve("company", "warmup")


@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT, "index.html"))


@app.get("/health")
def health():
    n = db.run_sql("select count(*) from deals")["rows"][0][0]
    return {"ok": True, "deals": n, "llm": bool(llm.API_KEY), "model": llm.MODEL}


@app.post("/api/ask")
def ask(body: Ask):
    if not _slots.acquire(timeout=60):
        raise HTTPException(503, "Band, bir ozdan keyin qayta urinib koʻring")
    try:
        return agent.ask(body.question.strip(), body.history)
    finally:
        _slots.release()
