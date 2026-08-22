import os
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ────────────────────────────────────────────────────────────────────
MONGO_URI     = os.getenv("MONGO_URI",     "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "travora")

# ── JWT ────────────────────────────────────────────────────────────────────────
SECRET_KEY                  = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

# ── LLM Provider ───────────────────────────────────────────────────────────────
# Primary provider:  anthropic | openai | gemini
LLM_PROVIDER      = os.getenv("LLM_PROVIDER", "gemini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY",    "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY",    "")
LLM_MODEL         = os.getenv("LLM_MODEL",         "gemini-2.5-flash-lite")

# ── LLM Resilience — Retry / Backoff ──────────────────────────────────────────
# Maximum number of retries per provider before giving up / falling back.
# Applies to transient 5xx errors.
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# Separate retry cap specifically for HTTP 429 quota errors.
# Kept low because quota errors rarely resolve within seconds — fail fast.
LLM_QUOTA_RETRIES = int(os.getenv("LLM_QUOTA_RETRIES", "2"))

# Initial exponential-backoff delay in seconds (doubled on each attempt, with jitter).
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "1.0"))

# Hard ceiling on backoff sleep regardless of how many retries have occurred.
LLM_RETRY_MAX_DELAY = float(os.getenv("LLM_RETRY_MAX_DELAY", "8.0"))

# Maximum Retry-After value (seconds) we will honour from the server.
# If the server says "retry after 429s", that is > this threshold, so we
# fail immediately instead of blocking for 7+ minutes.
# Set to 0 to always ignore Retry-After and use our own backoff.
LLM_MAX_RETRY_AFTER = float(os.getenv("LLM_MAX_RETRY_AFTER", "10.0"))

# ── LLM Resilience — Cache ─────────────────────────────────────────────────────
# TTL in seconds for in-memory response cache. 0 = disabled.
# Identical prompts within this window are served from cache (no API call).
LLM_CACHE_TTL = int(os.getenv("LLM_CACHE_TTL", "3600"))  # 1 hour

# Maximum number of entries held in the cache at once (FIFO eviction).
LLM_CACHE_MAX_SIZE = int(os.getenv("LLM_CACHE_MAX_SIZE", "256"))

# ── LLM Resilience — Rate Limiter ─────────────────────────────────────────────
# Requests per minute to allow through the token-bucket rate limiter.
# Set slightly below the free-tier limit to maintain headroom.
# Gemini free tier: 15 RPM — we default to 14. Set 0 to disable.
LLM_RATE_LIMIT_RPM = int(os.getenv("LLM_RATE_LIMIT_RPM", "14"))

# ── LLM Resilience — Fallback Provider ────────────────────────────────────────
# Provider to fall back to when the primary exhausts its quota.
# "" = auto-detect: try openai first (if key set), then anthropic, then fail.
# Explicit values: "openai" | "anthropic" | "none"
LLM_FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "")

# ── CORS origins (comma-separated) ────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500",
).split(",")
