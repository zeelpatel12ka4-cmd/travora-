"""
services/llm_resilience.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Production-grade resilience layer for all LLM API calls.

Layers (applied in order on every call_llm() invocation):
  1. TTL Cache         — identical prompts within TTL never hit the API again
  2. In-flight Dedup   — concurrent identical requests share one API call
  3. Rate Limiter      — token-bucket that caps RPM to avoid 429s proactively
  4. Retry + Fallback  — exponential backoff with jitter on 429/5xx,
                         then provider fallback, then friendly QuotaExhaustedError

All settings are loaded from environment variables (see config.py).
Zero external dependencies — stdlib only (asyncio, hashlib, time, logging).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple

logger = logging.getLogger("travora.llm")


# ─────────────────────────────────────────────────────────────────────────────
# Typed exception
# ─────────────────────────────────────────────────────────────────────────────

class QuotaExhaustedError(Exception):
    """
    Raised when all configured LLM providers have exhausted their quotas
    and no further retries will be attempted.

    Attributes:
        provider    — last provider attempted (e.g. "gemini")
        retry_after — recommended seconds to wait before trying again
                      (0 if unknown)
    """

    def __init__(self, provider: str, retry_after: float = 0, message: str = ""):
        self.provider = provider
        self.retry_after = retry_after
        self.message = message or (
            f"The AI service ({provider}) has reached its daily quota limit. "
            f"Please try again later."
            + (f" Estimated wait: {int(retry_after)}s." if retry_after else "")
        )
        super().__init__(self.message)


# ─────────────────────────────────────────────────────────────────────────────
# Retry configuration (loaded from env via config.py)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RetryConfig:
    """All tuneable knobs for the resilience layer."""
    max_retries: int       = 2       # retries for transient 5xx errors
    quota_retries: int     = 2       # separate retry cap for 429 quota errors
    base_delay: float      = 1.0     # initial backoff seconds
    max_delay: float       = 8.0     # cap on backoff — keeps total wait < 30s
    max_retry_after: float = 10.0    # ignore Retry-After values above this (seconds)
    cache_ttl: int         = 3600    # seconds; 0 = disabled
    cache_max_size: int    = 256     # max cached entries
    rate_limit_rpm: int    = 14      # requests per minute (0 = disabled)
    fallback_provider: str = ""      # "" = auto-detect from keys


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory TTL Cache
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    value: str
    expires_at: float  # monotonic clock


class LLMCache:
    """
    Thread-safe, async-compatible TTL cache backed by a plain dict.
    Uses SHA-256 of (system_prompt + user_message) as the cache key.
    Evicts the oldest entry when max_size is reached (simple FIFO).
    """

    def __init__(self, ttl: int, max_size: int):
        self._ttl = ttl
        self._max_size = max_size
        self._store: Dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def make_key(system_prompt: str, user_message: str) -> str:
        payload = f"{system_prompt}\x00{user_message}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> Optional[str]:
        if self._ttl == 0:
            return None
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                return None
            return entry.value

    async def set(self, key: str, value: str) -> None:
        if self._ttl == 0:
            return
        async with self._lock:
            # Evict oldest entry if at capacity
            if len(self._store) >= self._max_size and key not in self._store:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[key] = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + self._ttl,
            )

    @property
    def size(self) -> int:
        return len(self._store)


# ─────────────────────────────────────────────────────────────────────────────
# Token-Bucket Rate Limiter
# ─────────────────────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Async token-bucket rate limiter.
    Allows up to `rpm` requests per 60-second window.
    Callers that would exceed the limit sleep until a token is available.
    """

    def __init__(self, rpm: int):
        self._rpm = rpm
        self._tokens = float(rpm)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a rate-limit token is available."""
        if self._rpm <= 0:
            return  # disabled

        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                # Refill proportionally to elapsed time
                self._tokens = min(
                    float(self._rpm),
                    self._tokens + elapsed * (self._rpm / 60.0),
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return  # token acquired

                # Calculate how long to sleep for 1 token
                wait = (1.0 - self._tokens) / (self._rpm / 60.0)

            logger.info(
                "[LLM] RATE LIMIT — waiting %.2fs for token-bucket refill (RPM=%d)",
                wait, self._rpm,
            )
            await asyncio.sleep(wait)


# ─────────────────────────────────────────────────────────────────────────────
# In-flight request deduplicator
# ─────────────────────────────────────────────────────────────────────────────

class InflightDeduplicator:
    """
    Ensures that two concurrent calls with the same cache key share exactly
    one underlying API call instead of both hitting Gemini.
    """

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    async def get_lock(self, key: str) -> asyncio.Lock:
        async with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def release_key(self, key: str) -> None:
        async with self._meta_lock:
            self._locks.pop(key, None)


# ─────────────────────────────────────────────────────────────────────────────
# Backoff helpers
# ─────────────────────────────────────────────────────────────────────────────

def _jittered_backoff(attempt: int, base: float, cap: float) -> float:
    """
    Full-jitter exponential backoff (AWS recommended).
    delay = random(0, min(cap, base * 2^attempt))
    """
    upper = min(cap, base * (2 ** attempt))
    return random.uniform(0, upper)


def _extract_retry_after(exc: Exception) -> float:
    """
    Try to extract the server-recommended retry delay from a 429 exception.
    Handles google-generativeai, openai, and anthropic exception formats.
    Returns 0.0 if no delay is found.
    """
    # google-generativeai stores error metadata in various shapes
    for attr in ("retry_delay", "retry_after"):
        val = getattr(exc, attr, None)
        if val is not None:
            try:
                # retry_delay can be a proto object with .seconds
                if hasattr(val, "seconds"):
                    return float(val.seconds)
                return float(val)
            except (TypeError, ValueError):
                pass

    # Check string representation for "retry after X seconds"
    msg = str(exc).lower()
    for token in msg.split():
        try:
            val = float(token.rstrip("s."))
            if 0 < val < 3600:
                return val
        except ValueError:
            continue

    return 0.0


def _is_quota_error(exc: Exception) -> bool:
    """Return True if the exception is a 429 / quota-exceeded error."""
    msg = str(exc).lower()
    return any(k in msg for k in (
        "429", "quota", "rate limit", "resource exhausted",
        "too many requests", "ratexceeded",
    ))


def _is_retryable_error(exc: Exception) -> bool:
    """Return True if the exception is a transient server error (5xx)."""
    msg = str(exc).lower()
    return any(k in msg for k in (
        "500", "502", "503", "504", "internal server error",
        "bad gateway", "service unavailable", "gateway timeout",
        "deadline exceeded", "unavailable",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Singleton instances (initialised by setup_resilience_layer())
# ─────────────────────────────────────────────────────────────────────────────

_cache: Optional[LLMCache] = None
_rate_limiter: Optional[RateLimiter] = None
_deduplicator: InflightDeduplicator = InflightDeduplicator()
_config: RetryConfig = RetryConfig()


def setup_resilience_layer(cfg: RetryConfig) -> None:
    """
    Initialise the module-level singletons from a RetryConfig.
    Call this once during application startup (e.g. from lifespan).
    """
    global _cache, _rate_limiter, _config
    _config = cfg
    _cache = LLMCache(ttl=cfg.cache_ttl, max_size=cfg.cache_max_size)
    _rate_limiter = RateLimiter(rpm=cfg.rate_limit_rpm)
    logger.info(
        "[LLM] Resilience layer initialised — "
        "cache_ttl=%ds, cache_max=%d, rate_limit=%d RPM, "
        "max_retries=%d, quota_retries=%d, max_retry_after=%.0fs",
        cfg.cache_ttl, cfg.cache_max_size, cfg.rate_limit_rpm,
        cfg.max_retries, cfg.quota_retries, cfg.max_retry_after,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

ProviderFn = Callable[..., Coroutine[Any, Any, str]]


async def call_with_resilience(
    *,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
    primary_fn: ProviderFn,
    fallback_fn: Optional[ProviderFn],
    provider_name: str,
    fallback_name: str,
) -> str:
    """
    Execute a single LLM call through all resilience layers:
      cache → dedup → rate limit → retry(primary) → retry(fallback) → error

    Parameters
    ----------
    primary_fn      Async callable for the primary provider (Gemini by default).
    fallback_fn     Async callable for the fallback provider; None if not configured.
    provider_name   Human-readable name for logs ("gemini").
    fallback_name   Human-readable name for fallback logs ("openai").
    """
    if _cache is None or _rate_limiter is None:
        raise RuntimeError(
            "Resilience layer not initialised. "
            "Call setup_resilience_layer() during app startup."
        )

    # ── Layer 1: Cache lookup ─────────────────────────────────────────────────
    cache_key = LLMCache.make_key(system_prompt, user_message)
    cached = await _cache.get(cache_key)
    if cached is not None:
        logger.info("[LLM] CACHE HIT — key=%.12s…", cache_key)
        return cached

    # ── Layer 2: In-flight deduplication ─────────────────────────────────────
    inflight_lock = await _deduplicator.get_lock(cache_key)

    async with inflight_lock:
        # Re-check cache after acquiring lock (another coroutine may have
        # just completed the same request and populated the cache)
        cached = await _cache.get(cache_key)
        if cached is not None:
            logger.info(
                "[LLM] CACHE HIT (after dedup wait) — key=%.12s…", cache_key
            )
            return cached

        # ── Layer 3: Rate limiter ─────────────────────────────────────────────
        await _rate_limiter.acquire()

        # ── Layer 4: Retry primary provider ──────────────────────────────────
        result, last_exc = await _retry_provider(
            fn=primary_fn,
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
            provider_name=provider_name,
        )

        # ── Fallback provider ─────────────────────────────────────────────────
        if result is None and fallback_fn is not None:
            logger.warning(
                "[LLM] FALLBACK — primary provider '%s' exhausted. "
                "Switching to '%s'. Original error: %s",
                provider_name, fallback_name, last_exc,
            )
            result, last_exc = await _retry_provider(
                fn=fallback_fn,
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model,
                provider_name=fallback_name,
            )

        if result is None:
            retry_after = _extract_retry_after(last_exc) if last_exc else 0
            logger.error(
                "[LLM] QUOTA EXHAUSTED — all providers failed. "
                "Last error: %s | retry_after=%.0fs",
                last_exc, retry_after,
            )
            raise QuotaExhaustedError(
                provider=provider_name,
                retry_after=retry_after,
            )

        # ── Populate cache ────────────────────────────────────────────────────
        await _cache.set(cache_key, result)
        return result


async def _retry_provider(
    *,
    fn: ProviderFn,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
    provider_name: str,
) -> Tuple[Optional[str], Optional[Exception]]:
    """
    Attempt to call `fn` with automatic retry on transient failures.

    Retry strategy:
    - Quota errors (429)  : up to _config.quota_retries attempts.
                            Retry-After values > _config.max_retry_after cause
                            immediate fail-fast (no sleeping for minutes).
    - Transient 5xx       : up to _config.max_retries attempts with
                            full-jitter exponential backoff.
    - Non-retryable errors: break immediately (auth failures, bad requests).

    Returns (result, None) on success or (None, last_exc) on total failure.
    """
    last_exc: Optional[Exception] = None
    quota_attempt = 0   # separate counter for 429 errors
    transient_attempt = 0  # separate counter for 5xx errors

    # Total iterations = max of either cap + 1 for the initial attempt.
    # We break early based on per-type counters below.
    max_iterations = max(_config.quota_retries, _config.max_retries) + 1

    for attempt in range(max_iterations):
        try:
            result = await fn(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model,
            )
            if attempt > 0:
                logger.info(
                    "[LLM] RETRY SUCCESS — provider=%s attempt=%d",
                    provider_name, attempt + 1,
                )
            return result, None

        except Exception as exc:
            last_exc = exc
            is_quota     = _is_quota_error(exc)
            is_transient = _is_retryable_error(exc) and not is_quota

            # ── Non-retryable (auth, bad request, JSON, etc.) ────────────────
            if not (is_quota or is_transient):
                logger.error(
                    "[LLM] NON-RETRYABLE ERROR — provider=%s: %s",
                    provider_name, exc,
                )
                break

            # ── Quota error (HTTP 429) ────────────────────────────────────────
            if is_quota:
                server_delay = _extract_retry_after(exc)

                # FAIL-FAST: Retry-After is longer than our tolerance.
                # Sleeping for hundreds of seconds is unacceptable in a
                # request/response cycle — return immediately so the caller
                # can show a clean error to the user.
                if server_delay > _config.max_retry_after:
                    logger.warning(
                        "[LLM] QUOTA FAIL-FAST — provider=%s: server wants "
                        "%.0fs retry delay > max_retry_after=%.0fs. "
                        "Failing immediately.",
                        provider_name, server_delay, _config.max_retry_after,
                    )
                    break

                quota_attempt += 1
                if quota_attempt > _config.quota_retries:
                    logger.warning(
                        "[LLM] QUOTA MAX RETRIES — provider=%s exhausted "
                        "%d quota retry attempts.",
                        provider_name, _config.quota_retries,
                    )
                    break

                # Use server_delay only when it's within tolerance,
                # otherwise use jittered backoff (which is also capped).
                if 0 < server_delay <= _config.max_retry_after:
                    sleep_for = server_delay
                    logger.warning(
                        "[LLM] RETRY-AFTER — provider=%s honouring server "
                        "delay of %.0fs (quota attempt %d/%d)",
                        provider_name, sleep_for,
                        quota_attempt, _config.quota_retries,
                    )
                else:
                    sleep_for = _jittered_backoff(
                        quota_attempt - 1, _config.base_delay, _config.max_delay
                    )
                    logger.warning(
                        "[LLM] QUOTA RETRY — provider=%s sleeping %.2fs "
                        "(quota attempt %d/%d)",
                        provider_name, sleep_for,
                        quota_attempt, _config.quota_retries,
                    )

                await asyncio.sleep(sleep_for)
                continue

            # ── Transient 5xx error ───────────────────────────────────────────
            if is_transient:
                transient_attempt += 1
                if transient_attempt > _config.max_retries:
                    logger.warning(
                        "[LLM] TRANSIENT MAX RETRIES — provider=%s exhausted "
                        "%d retry attempts.",
                        provider_name, _config.max_retries,
                    )
                    break

                sleep_for = _jittered_backoff(
                    transient_attempt - 1, _config.base_delay, _config.max_delay
                )
                logger.warning(
                    "[LLM] RETRY — provider=%s sleeping %.2fs before attempt "
                    "%d/%d (5xx transient error: %s)",
                    provider_name, sleep_for,
                    transient_attempt, _config.max_retries,
                    str(exc)[:120],
                )
                await asyncio.sleep(sleep_for)
                continue

    return None, last_exc
