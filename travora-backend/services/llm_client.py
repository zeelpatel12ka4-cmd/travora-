"""
services/llm_client.py
~~~~~~~~~~~~~~~~~~~~~~
Thin wrapper around LLM provider APIs.

Supports Anthropic Claude, OpenAI, and Google Gemini — switch via LLM_PROVIDER env var.

All calls flow through the resilience layer (services/llm_resilience.py) which provides:
  - TTL response cache (identical prompts served without hitting the API)
  - In-flight request deduplication (concurrent identical calls share one API call)
  - Proactive token-bucket rate limiting (avoids 429s before they happen)
  - Exponential backoff with full jitter on 429 / 5xx errors
  - Respects Retry-After / retry_delay header from Gemini
  - Automatic fallback to a secondary provider if primary quota is exhausted
  - QuotaExhaustedError raised when all providers fail (caught in routes/planner.py)
"""
from __future__ import annotations

import json
import re
import logging
from typing import Optional

from config import (
    LLM_PROVIDER,
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    LLM_MODEL,
    LLM_MAX_RETRIES,
    LLM_QUOTA_RETRIES,
    LLM_RETRY_BASE_DELAY,
    LLM_RETRY_MAX_DELAY,
    LLM_MAX_RETRY_AFTER,
    LLM_CACHE_TTL,
    LLM_CACHE_MAX_SIZE,
    LLM_RATE_LIMIT_RPM,
    LLM_FALLBACK_PROVIDER,
)
from services.llm_resilience import (
    RetryConfig,
    QuotaExhaustedError,
    call_with_resilience,
    setup_resilience_layer,
)

logger = logging.getLogger("travora.llm")

# Re-export so callers don't need to import from two places
__all__ = ["call_llm", "safe_parse_json", "QuotaExhaustedError", "initialise_llm"]


# ─────────────────────────────────────────────────────────────────────────────
# One-time startup initialisation
# ─────────────────────────────────────────────────────────────────────────────

def initialise_llm() -> None:
    """
    Wire up the resilience layer with settings from config.py.
    Must be called once during application startup (see main.py lifespan).
    """
    cfg = RetryConfig(
        max_retries=LLM_MAX_RETRIES,
        quota_retries=LLM_QUOTA_RETRIES,
        base_delay=LLM_RETRY_BASE_DELAY,
        max_delay=LLM_RETRY_MAX_DELAY,
        max_retry_after=LLM_MAX_RETRY_AFTER,
        cache_ttl=LLM_CACHE_TTL,
        cache_max_size=LLM_CACHE_MAX_SIZE,
        rate_limit_rpm=LLM_RATE_LIMIT_RPM,
        fallback_provider=LLM_FALLBACK_PROVIDER,
    )
    setup_resilience_layer(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# Fallback provider resolution
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_fallback() -> tuple[str, Optional[object]]:
    """
    Determine which provider to fall back to when the primary is exhausted.

    Priority:
      1. LLM_FALLBACK_PROVIDER env var (explicit override)
      2. openai  — if OPENAI_API_KEY is set
      3. anthropic — if ANTHROPIC_API_KEY is set
      4. None    — no fallback available

    Returns (provider_name, provider_callable_or_None).
    The callable matches the _call_* function signatures.
    """
    explicit = LLM_FALLBACK_PROVIDER.lower().strip()

    candidates: list[tuple[str, str, object]] = [
        ("openai",    OPENAI_API_KEY,    _call_openai),
        ("anthropic", ANTHROPIC_API_KEY, _call_anthropic),
    ]

    if explicit in ("none", "disabled", "off"):
        return "", None

    if explicit in ("openai", "anthropic"):
        for name, key, fn in candidates:
            if name == explicit:
                if key:
                    return name, fn
                logger.warning(
                    "[LLM] Fallback provider '%s' configured but API key is missing — "
                    "no fallback will be used.", explicit
                )
                return "", None

    # Auto-detect: try in priority order
    for name, key, fn in candidates:
        if key:
            return name, fn

    return "", None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    model: Optional[str] = None,
) -> str:
    """
    Call the configured LLM through the full resilience stack and return plain text.

    Raises QuotaExhaustedError if all providers are exhausted after retries.
    Callers are responsible for JSON parsing (use safe_parse_json).
    """
    target_model = model or LLM_MODEL

    # Map provider name → primary callable
    provider_map: dict[str, object] = {
        "anthropic": _call_anthropic,
        "openai":    _call_openai,
        "gemini":    _call_gemini,
    }

    primary_fn = provider_map.get(LLM_PROVIDER)
    if primary_fn is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}. "
            "Set to 'anthropic', 'openai', or 'gemini'."
        )

    # Determine fallback (different provider from primary)
    fallback_name, fallback_fn = _resolve_fallback()
    # Don't fall back to the same provider we're already using
    if fallback_name == LLM_PROVIDER:
        fallback_name, fallback_fn = "", None

    return await call_with_resilience(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=max_tokens,
        temperature=temperature,
        model=target_model,
        primary_fn=primary_fn,
        fallback_fn=fallback_fn,
        provider_name=LLM_PROVIDER,
        fallback_name=fallback_name or "none",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Provider implementations (raw, no resilience — called by resilience layer)
# ─────────────────────────────────────────────────────────────────────────────

async def _call_anthropic(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment variables.")

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


async def _call_openai(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
) -> str:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    return response.choices[0].message.content


async def _call_gemini(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai package not installed. "
            "Run: pip install google-generativeai"
        )

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")

    genai.configure(api_key=GEMINI_API_KEY)

    gemini_model = genai.GenerativeModel(
        model_name=model,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
        system_instruction=system_prompt,
    )

    response = await gemini_model.generate_content_async(user_message)
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
# JSON parsing utility
# ─────────────────────────────────────────────────────────────────────────────

def safe_parse_json(text: str) -> dict:
    """
    Robustly extract and parse the first JSON object or array from an LLM response.

    Handles all common Gemini output quirks:
    - Markdown fences (```json ... ```) with or without trailing text/newlines
    - Responses that are pure JSON with no fences
    - Truncated responses (output cut off mid-JSON due to token limits)
    - String values containing brackets/braces (e.g. "Visit the [fort]")
    """
    # ── 1. Strip markdown code fences ────────────────────────────────────────
    fence_match = re.search(r"```(?:json|JSON)?\s*\n([\s\S]*?)```", text)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        cleaned = text.strip()

    # ── 2. Locate the start of the JSON structure ─────────────────────────────
    start = -1
    for i, ch in enumerate(cleaned):
        if ch in ("{", "["):
            start = i
            break

    if start == -1:
        raise ValueError(f"No JSON found in LLM response:\n{text[:500]}")

    candidate = cleaned[start:]

    # ── 3. Fast path: direct parse (works when output is complete) ────────────
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # ── 4. String-aware bracket scanner ──────────────────────────────────────
    # Correctly handles braces/brackets that appear inside quoted strings.
    opener = candidate[0]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escape_next = False
    end = -1

    for i, ch in enumerate(candidate):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end != -1:
        try:
            return json.loads(candidate[:end])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Found JSON boundaries but failed to parse "
                f"(response may be truncated — increase max_tokens): {exc}\n{text[:300]}"
            ) from exc

    # ── 5. Truncation recovery — walk backwards and close open structures ─────
    for trim_end in range(len(candidate), 0, -1):
        chunk = candidate[:trim_end].rstrip().rstrip(",")
        stack: list[str] = []
        in_str = False
        esc = False
        for ch in chunk:
            if esc:
                esc = False
                continue
            if ch == "\\" and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in ("{", "["):
                stack.append("}" if ch == "{" else "]")
            elif ch in ("}", "]") and stack and stack[-1] == ch:
                stack.pop()

        closing = "".join(reversed(stack))
        try:
            return json.loads(chunk + closing)
        except json.JSONDecodeError:
            continue

    raise ValueError(
        f"Could not parse JSON from LLM response "
        f"(likely truncated — check max_tokens setting):\n{text[:500]}"
    )
