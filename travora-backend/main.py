import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from database.mongo import connect_db, close_db
from routes import auth, trips, destinations, planner, admin
from services.llm_client import initialise_llm

# ── Logging — structured, level-controlled via LOG_LEVEL env var ───────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("travora")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage DB connection and LLM initialisation across app lifetime."""
    await connect_db()

    # Initialise the LLM resilience layer (cache, rate limiter, retry config).
    # This must happen after the event loop is running (hence here, not at
    # module level) because asyncio.Lock objects require a running loop.
    initialise_llm()
    logger.info("[Startup] LLM resilience layer ready")

    yield

    await close_db()


app = FastAPI(
    title="Travora API",
    description="AI-powered travel planning backend",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS — allow all localhost ports for local development ─────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],       # file:// direct-open
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",  # any localhost port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/auth",         tags=["Auth"])
app.include_router(trips.router,        prefix="/api/trips",        tags=["Trips"])
app.include_router(destinations.router, prefix="/api/destinations", tags=["Destinations"])
app.include_router(planner.router,      prefix="/api/planner",      tags=["Planner"])
app.include_router(admin.router,        prefix="/api/admin",        tags=["Admin"])


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "Travora API is running"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.png", include_in_schema=False)
async def favicon():
    favicon_path = os.path.join(os.path.dirname(__file__), "favicon.png")
    return FileResponse(favicon_path, media_type="image/png")
