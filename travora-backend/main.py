from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database.mongo import connect_db, close_db
from routes import auth, trips, destinations, planner


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage DB connection across app lifetime."""
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="Travora API",
    description="AI-powered travel planning backend",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS — allow all localhost ports for local development ─────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],       # file:// direct-open
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",  # any localhost port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/auth",         tags=["Auth"])
app.include_router(trips.router,        prefix="/api/trips",        tags=["Trips"])
app.include_router(destinations.router, prefix="/api/destinations", tags=["Destinations"])
app.include_router(planner.router,      prefix="/api/planner",      tags=["Planner"])


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "Travora API is running"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
