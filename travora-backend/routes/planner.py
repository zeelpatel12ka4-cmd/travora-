from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional

from database.mongo import get_db
from database.models import PlannerRequest, PlannerResponse, TripStatus
from services.auth_service import get_current_user_id
from services.llm_client import QuotaExhaustedError
from agents.orchestrator import Orchestrator

router = APIRouter()


@router.post("/generate", response_model=PlannerResponse)
async def generate_trip(
    payload: PlannerRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Run the full multi-agent planning pipeline and persist the result.
    This is a synchronous (awaited) call — the client waits for completion.
    For production, consider streaming or a background job with polling.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    # ── Create or locate the trip document ────────────────────────────────────
    if payload.trip_id:
        try:
            trip_oid = ObjectId(payload.trip_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid trip_id")

        existing = await db.trips.find_one({"_id": trip_oid, "user_id": ObjectId(user_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Trip not found")

        # Mark as generating
        await db.trips.update_one(
            {"_id": trip_oid},
            {"$set": {"status": TripStatus.generating, "updated_at": now}},
        )
        trip_id_str = payload.trip_id
    else:
        # Create a new trip document
        trip_doc = {
            "user_id":         ObjectId(user_id),
            "destination":     payload.destination,
            "from_city":       payload.from_city,
            "start_date":      payload.start_date,
            "end_date":        payload.end_date,
            "travelers":       payload.travelers,
            "budget":          payload.budget,
            "currency":        payload.currency,
            "interests":       payload.interests,
            "status":          TripStatus.generating,
            "itinerary":       [],
            "budget_breakdown":{},
            "agent_notes":     {},
            "created_at":      now,
            "updated_at":      now,
        }
        result    = await db.trips.insert_one(trip_doc)
        trip_id_str = str(result.inserted_id)
        trip_oid    = result.inserted_id

    # ── Run the agent pipeline ─────────────────────────────────────────────────
    try:
        orchestrator = Orchestrator()
        output = await orchestrator.run(
            destination=payload.destination,
            from_city=payload.from_city,
            start_date=payload.start_date,
            end_date=payload.end_date,
            travelers=payload.travelers,
            budget=payload.budget,
            currency=payload.currency,
            interests=payload.interests,
        )

    except QuotaExhaustedError as qe:
        # Mark trip back to draft so user can retry later
        await db.trips.update_one(
            {"_id": trip_oid},
            {"$set": {
                "status":     TripStatus.draft,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        # Build a user-friendly error detail
        detail: dict = {
            "error":       "quota_exhausted",
            "provider":    qe.provider,
            "message":     qe.message,
        }
        if qe.retry_after:
            detail["retry_after_seconds"] = int(qe.retry_after)
            detail["retry_after_human"]   = _humanise_seconds(int(qe.retry_after))

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )

    except Exception as e:
        # Generic pipeline failure — mark trip as draft, re-raise as 500
        await db.trips.update_one(
            {"_id": trip_oid},
            {"$set": {
                "status":     TripStatus.draft,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent pipeline failed: {str(e)}",
        )

    # ── Persist results ────────────────────────────────────────────────────────
    await db.trips.update_one(
        {"_id": trip_oid},
        {
            "$set": {
                "status":           TripStatus.generated,
                "itinerary":        output["itinerary"],
                "budget_breakdown": output["budget_breakdown"],
                "agent_notes":      output["agent_notes"],
                "local_tips":       output.get("local_tips",  {}),
                "research":         output.get("research",    {}),
                "updated_at":       datetime.now(timezone.utc),
            }
        },
    )

    return PlannerResponse(
        trip_id=trip_id_str,
        status="generated",
        message=f"Your {payload.destination} itinerary is ready!",
        itinerary=output["itinerary"],
        budget_breakdown=output["budget_breakdown"],
        agent_notes=output["agent_notes"],
    )


@router.get("/status/{trip_id}")
async def get_generation_status(
    trip_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Poll endpoint to check if a trip is still generating."""
    db = get_db()
    try:
        oid = ObjectId(trip_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid trip ID")

    doc = await db.trips.find_one(
        {"_id": oid, "user_id": ObjectId(user_id)},
        {"status": 1, "destination": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Trip not found")

    return {"trip_id": trip_id, "status": doc.get("status", "unknown")}


@router.post("/regenerate/{trip_id}", response_model=PlannerResponse)
async def regenerate_trip(
    trip_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Re-run the full agent pipeline for an existing trip."""
    db = get_db()
    try:
        oid = ObjectId(trip_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid trip ID")

    doc = await db.trips.find_one({"_id": oid, "user_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Trip not found")

    regenerate_request = PlannerRequest(
        destination=doc["destination"],
        from_city=doc["from_city"],
        start_date=doc["start_date"],
        end_date=doc["end_date"],
        travelers=doc["travelers"],
        budget=doc["budget"],
        currency=doc.get("currency", "INR"),
        interests=doc.get("interests", []),
        trip_id=trip_id,
    )
    return await generate_trip(regenerate_request, user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _humanise_seconds(seconds: int) -> str:
    """Convert a raw second count into a human-readable string."""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    return f"{hours} hour{'s' if hours != 1 else ''}"
