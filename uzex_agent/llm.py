import os
import streamlit as st
import httpx
from dotenv import load_dotenv


load_dotenv()

def get_setting(name: str, default: str = "") -> str:
    """Avval Streamlit Secrets, keyin lokal .env/environment."""
    try:
        value = st.secrets.get(name)
        if value is not None:
            return str(value)
    except Exception:
        pass

    return os.getenv(name, default)


PROVIDER = get_setting("LLM_PROVIDER", "anthropic").lower()

DEFAULTS = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o",
}

MODEL = get_setting("LLM_MODEL") or DEFAULTS.get(PROVIDER, "")
API_KEY = get_setting("LLM_API_KEY")
BASE_URL = get_setting("LLM_BASE_URL")


class LLMError(Exception):
    pass


_client = httpx.Client(limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=60))


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    last = None
    for attempt in range(3):
        try:
            r = _client.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504, 529):
                last = f"{r.status_code}: {r.text[:200]}"
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise LLMError(f"{r.status_code}: {r.text[:300]}")
            return r.json()
        except httpx.HTTPError as e:
            last = str(e)
            time.sleep(1.0)
    raise LLMError(last or "LLM javob bermadi")


def chat(system: str, messages: list, tools: list, timeout: float = 45) -> dict:
    """Javob: {"text": str, "calls": [{"id","name","args"}]}. messages — ichki format."""
    if not API_KEY:
        raise LLMError("LLM_API_KEY oʻrnatilmagan")
    if PROVIDER == "anthropic":
        return _anthropic(system, messages, tools, timeout)
    return _openai(system, messages, tools, timeout)


def _anthropic(system, messages, tools, timeout):
    out = []
    for m in messages:
        if m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["id"], "content": m["content"]}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        elif m["role"] == "assistant":
            content = []
            if m.get("text"):
                content.append({"type": "text", "text": m["text"]})
            for c in m.get("calls", []):
                content.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]})
            out.append({"role": "assistant", "content": content})
        else:
            out.append({"role": "user", "content": m["content"]})
    data = _post(
        (BASE_URL or "https://api.anthropic.com") + "/v1/messages",
        {"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        {
            "model": MODEL,
            "max_tokens": 2000,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": out,
            "tools": tools,
        },
        timeout,
    )
    text, calls = "", []
    for b in data.get("content", []):
        if b["type"] == "text":
            text += b["text"]
        elif b["type"] == "tool_use":
            calls.append({"id": b["id"], "name": b["name"], "args": b["input"]})
    return {"text": text, "calls": calls}


def _openai(system, messages, tools, timeout):
    out = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
        elif m["role"] == "assistant":
            msg = {"role": "assistant", "content": m.get("text") or ""}
            if m.get("calls"):
                msg["tool_calls"] = [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": json.dumps(c["args"], ensure_ascii=False)}}
                    for c in m["calls"]
                ]
            out.append(msg)
        else:
            out.append({"role": "user", "content": m["content"]})
    data = _post(
        (BASE_URL or "https://api.openai.com/v1") + "/chat/completions",
        {"Authorization": f"Bearer {API_KEY}", "content-type": "application/json"},
        {
            "model": MODEL,
            "messages": out,
            "tools": [
                {"type": "function",
                 "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
                for t in tools
            ],
        },
        timeout,
    )
    msg = data["choices"][0]["message"]
    calls = []
    for c in msg.get("tool_calls") or []:
        try:
            args = json.loads(c["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": c["id"], "name": c["function"]["name"], "args": args})
    return {"text": msg.get("content") or "", "calls": calls}