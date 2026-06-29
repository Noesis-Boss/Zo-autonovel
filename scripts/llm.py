"""
llm.py — unified LLM client for the Zo-autonovel pipeline.

Tries providers in order: Anthropic (claude-sonnet-4-5) → Zo /ask
(via the Zo API). Configure with env vars:

  ANTHROPIC_API_KEY   primary key for Anthropic
  ZO_ASK_MODEL        default "claude-sonnet-4-5"
  ZO_HOST             default "https://api.zo.computer"

Falls back to Zo /ask when ANTHROPIC_API_KEY is missing, when the
account has no credit (HTTP 400/402 from Anthropic), or when the user
sets LLM_PROVIDER=zo. Both providers expose chat() with the same
signature so callers don't need to branch.

Usage:
  from llm import chat
  text = chat([{"role": "user", "content": "Hello"}], max_tokens=1024)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ZO_ASK_URL = os.environ.get("ZO_HOST", "https://api.zo.computer") + "/zo/ask"

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
ZO_DEFAULT_MODEL = os.environ.get("ZO_ASK_MODEL", DEFAULT_MODEL)


class LLMError(RuntimeError):
    pass


def _anthropic_chat(messages, *, model, max_tokens, temperature, system, timeout):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    payload = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        payload["system"] = system
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_URL, data=body, method="POST",
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
        if e.code in (400, 402, 403):
            # 400 credit / 402 payment required / 403 permission — fall back
            os.environ["_LLM_FALLBACK_REASON"] = (
                f"anthropic_{e.code}: {body[:200]}")
            return None
        raise LLMError(f"anthropic {e.code}: {body[:500]}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"anthropic connection: {e.reason}") from None

    parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts).strip() or None


def _zo_chat(messages, *, model, max_tokens, temperature, system, timeout):
    token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
    if not token:
        raise LLMError("ZO_CLIENT_IDENTITY_TOKEN not set; cannot use Zo fallback")
    prompt_parts = []
    if system:
        prompt_parts.append(system.strip() + "\n\n")
    for m in messages:
        role = m.get("role", "user")
        if role == "user":
            prompt_parts.append(m["content"])
        elif role == "assistant":
            prompt_parts.append(f"\n[assistant]: {m['content']}")
    prompt = "\n".join(prompt_parts)
    payload = {
        "input": prompt,
        "model_name": model or ZO_DEFAULT_MODEL,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ZO_ASK_URL, data=body, method="POST",
        headers={
            "authorization": token,
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise LLMError(f"zo /ask {e.code}: {body[:500]}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"zo /ask connection: {e.reason}") from None

    if isinstance(data, dict):
        if data.get("output"):
            return str(data["output"]).strip()
        if data.get("content"):
            return str(data["content"]).strip()
        if data.get("text"):
            return str(data["text"]).strip()
    raise LLMError(f"zo /ask empty response: {json.dumps(data)[:300]}")


def chat(messages, *, model=None, max_tokens=4096, temperature=1.0,
         system=None, timeout=600, provider=None):
    """Single-shot chat. Returns concatenated assistant text.

    provider: 'anthropic' | 'zo' | None (auto). If None, tries anthropic
    first then zo. Set LLM_PROVIDER env var to force one path.
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "auto")
    last_err: LLMError | None = None

    if provider in ("anthropic", "auto"):
        try:
            text = _anthropic_chat(messages, model=model, max_tokens=max_tokens,
                                   temperature=temperature, system=system,
                                   timeout=timeout)
            if text:
                return text
            if provider == "anthropic":
                raise LLMError("anthropic returned empty / fallback disabled")
        except LLMError as e:
            if provider == "anthropic":
                raise
            last_err = e

    if provider in ("zo", "auto"):
        try:
            return _zo_chat(messages, model=model, max_tokens=max_tokens,
                            temperature=temperature, system=system,
                            timeout=timeout)
        except LLMError as e:
            last_err = e

    raise last_err or LLMError("no LLM provider available")
