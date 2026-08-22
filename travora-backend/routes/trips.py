from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from database.mongo import get_db
from database.models import (
    TripCreate, TripOut, TripUpdate, TripStatus,
    ItineraryDay, BudgetBreakdown, AgentNotes,
)
from services.auth_service import get_current_user_id

router = APIRouter()


def _format_trip(doc: dict) -> TripOut:
    itinerary = [ItineraryDay(**day) for day in doc.get("itinerary", [])]
    bd_data = doc.get("budget_breakdown", {})
    budget_breakdown = BudgetBreakdown(**bd_data) if bd_data else BudgetBreakdown()
    an_data = doc.get("agent_notes", {})
    agent_notes = AgentNotes(**an_data) if an_data else AgentNotes()

    return TripOut(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        destination=doc["destination"],
        from_city=doc["from_city"],
        start_date=doc["start_date"],
        end_date=doc["end_date"],
        travelers=doc["travelers"],
        budget=doc["budget"],
        currency=doc.get("currency", "INR"),
        status=doc.get("status", TripStatus.draft),
        itinerary=itinerary,
        budget_breakdown=budget_breakdown,
        agent_notes=agent_notes,
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at"),
    )


@router.post("/", response_model=TripOut, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: TripCreate,
    user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": ObjectId(user_id),
        "destination": payload.destination,
        "from_city": payload.from_city,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "travelers": payload.travelers,
        "budget": payload.budget,
        "currency": payload.currency,
        "interests": payload.interests,
        "status": TripStatus.draft,
        "itinerary": [],
        "budget_breakdown": {},
        "agent_notes": {},
        "created_at": now,
        "updated_at": now,
    }
    result = await db.trips.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _format_trip(doc)


@router.get("/", response_model=List[TripOut])
async def list_trips(
    user_id: str = Depends(get_current_user_id),
    status_filter: Optional[TripStatus] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    query: dict = {"user_id": ObjectId(user_id)}
    if status_filter:
        query["status"] = status_filter

    cursor = db.trips.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_format_trip(d) for d in docs]


@router.get("/{trip_id}", response_model=TripOut)
async def get_trip(
    trip_id: str,
    user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    try:
        oid = ObjectId(trip_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid trip ID")

    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    is_admin = user_doc.get("is_admin", False) if user_doc else False
    query = {"_id": oid} if is_admin else {"_id": oid, "user_id": ObjectId(user_id)}

    doc = await db.trips.find_one(query)
    if not doc:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _format_trip(doc)


@router.put("/{trip_id}", response_model=TripOut)
async def update_trip(
    trip_id: str,
    payload: TripUpdate,
    user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    try:
        oid = ObjectId(trip_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid trip ID")

    doc = await db.trips.find_one({"_id": oid, "user_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Trip not found")

    update_fields: dict = {"updated_at": datetime.now(timezone.utc)}
    for field, value in payload.model_dump(exclude_none=True).items():
        update_fields[field] = value

    await db.trips.update_one({"_id": oid}, {"$set": update_fields})
    updated = await db.trips.find_one({"_id": oid})
    return _format_trip(updated)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    trip_id: str,
    user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    try:
        oid = ObjectId(trip_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid trip ID")

    result = await db.trips.delete_one({"_id": oid, "user_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Trip not found")
