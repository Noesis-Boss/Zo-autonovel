"""
claude_api.py — minimal Anthropic Messages API wrapper.

Used by foundation.py, drafting.py, revision.py. No external deps.
Reads ANTHROPIC_API_KEY from environment; defaults to claude-sonnet-4-5.

Usage:
  from claude_api import chat
  text = chat([{"role": "user", "content": "Hello"}], max_tokens=1024)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
ANTHROPIC_VERSION = "2023-06-01"


class APIError(RuntimeError):
    pass


def chat(messages: list[dict], *, model: str | None = None, max_tokens: int = 4096,
         temperature: float = 1.0, system: str | None = None,
         timeout: int = 600) -> str:
    """Single-shot Anthropic Messages call. Returns concatenated text.

    messages: list of {role: "user"|"assistant", content: str}
    system: optional system prompt (str)
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise APIError("ANTHROPIC_API_KEY not set")

    payload: dict = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        payload["system"] = system

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise APIError(f"{e.code} {e.reason}: {body[:500]}") from None
    except urllib.error.URLError as e:
        raise APIError(f"connection error: {e.reason}") from None

    parts: list[str] = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    text = "".join(parts).strip()
    if not text:
        raise APIError(f"empty response: {json.dumps(data)[:500]}")
    return text


def stream_chunks(messages: list[dict], **kwargs):
    """Yield text chunks as they arrive. Disabled by default (not used
    by current pipeline). Left here for future streaming support."""
    raise NotImplementedError("streaming not enabled in this scaffold")