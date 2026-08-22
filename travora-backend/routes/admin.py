import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from database.mongo import get_db
from database.models import UserAdminOut, TripAdminOut, TripStatus
from services.auth_service import get_current_admin_id

router = APIRouter()


# ─────────────────────────────────────────────────────────────
# 1. Overview Stats
# ─────────────────────────────────────────────────────────────
@router.get("/stats/overview")
async def get_overview_stats(admin_id: str = Depends(get_current_admin_id)):
    db = get_db()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"is_active": {"$ne": False}})
    total_trips = await db.trips.count_documents({})
    trips_this_week = await db.trips.count_documents({"created_at": {"$gte": week_ago}})
    trips_this_month = await db.trips.count_documents({"created_at": {"$gte": month_ago}})

    # Status counts
    generated_trips = await db.trips.count_documents({"status": TripStatus.generated})
    booked_trips = await db.trips.count_documents({"status": TripStatus.booked})
    draft_trips = await db.trips.count_documents({"status": TripStatus.draft})
    generating_trips = await db.trips.count_documents({"status": TripStatus.generating})

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_trips": total_trips,
        "trips_this_week": trips_this_week,
        "trips_this_month": trips_this_month,
        "generated_trips": generated_trips,
        "booked_trips": booked_trips,
        "draft_trips": draft_trips,
        "generating_trips": generating_trips,
    }


# ─────────────────────────────────────────────────────────────
# 2. Top Destinations (Top 10)
# ─────────────────────────────────────────────────────────────
@router.get("/stats/top-destinations")
async def top_destinations(admin_id: str = Depends(get_current_admin_id)):
    db = get_db()
    pipeline = [
        {"$match": {"destination": {"$ne": None, "$nin": ["", None]}}},
        {"$group": {"_id": "$destination", "trip_count": {"$sum": 1}}},
        {"$sort": {"trip_count": -1}},
        {"$limit": 10},
    ]
    results = await db.trips.aggregate(pipeline).to_list(length=10)
    return [{"destination": r["_id"], "trip_count": r["trip_count"]} for r in results]


# ─────────────────────────────────────────────────────────────
# 3. Top Interests (Top 10)
# ─────────────────────────────────────────────────────────────
@router.get("/stats/top-interests")
async def top_interests(admin_id: str = Depends(get_current_admin_id)):
    db = get_db()
    pipeline = [
        {"$match": {"interests": {"$exists": True, "$ne": []}}},
        {"$unwind": "$interests"},
        {"$match": {"interests": {"$nin": ["", None]}}},
        {"$group": {"_id": "$interests", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    results = await db.trips.aggregate(pipeline).to_list(length=10)
    return [{"interest": r["_id"], "count": r["count"]} for r in results]


# ─────────────────────────────────────────────────────────────
# 6. Engagement (Trips per day over last 30 days)
# ─────────────────────────────────────────────────────────────
@router.get("/stats/engagement")
async def get_engagement_stats(admin_id: str = Depends(get_current_admin_id)):
    db = get_db()
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)

    pipeline = [
        {"$match": {"created_at": {"$gte": start_date}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$created_at",
                    }
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    results = await db.trips.aggregate(pipeline).to_list(length=100)
    count_map = {r["_id"]: r["count"] for r in results if r.get("_id")}

    # Build continuous 30-day timeline
    engagement = []
    for i in range(29, -1, -1):
        day_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        engagement.append({
            "date": day_str,
            "count": count_map.get(day_str, 0),
        })

    return engagement


# ─────────────────────────────────────────────────────────────
# 4. User Management (List & Soft-deactivate)
# ─────────────────────────────────────────────────────────────
@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    status: Optional[str] = Query(None, description="Filter by active status: 'active' | 'inactive'"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    admin_id: str = Depends(get_current_admin_id),
):
    db = get_db()
    match_conditions = []

    if search and search.strip():
        term = search.strip()
        match_conditions.append({
            "$or": [
                {"name": {"$regex": term, "$options": "i"}},
                {"email": {"$regex": term, "$options": "i"}},
            ]
        })

    if status == "active":
        match_conditions.append({"is_active": {"$ne": False}})
    elif status == "inactive":
        match_conditions.append({"is_active": False})

    match_filter = {"$and": match_conditions} if match_conditions else {}

    total = await db.users.count_documents(match_filter)

    pipeline = [
        {"$match": match_filter},
        {
            "$lookup": {
                "from": "trips",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "user_trips",
            }
        },
        {"$sort": {"created_at": -1}},
        {"$skip": (page - 1) * limit},
        {"$limit": limit},
    ]

    docs = await db.users.aggregate(pipeline).to_list(length=limit)

    users_list = []
    for doc in docs:
        users_list.append(UserAdminOut(
            id=str(doc["_id"]),
            name=doc.get("name", ""),
            email=doc.get("email", ""),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
            trip_count=len(doc.get("user_trips", [])),
            is_active=doc.get("is_active", True),
            is_admin=doc.get("is_admin", False),
        ))

    total_pages = max(1, math.ceil(total / limit))
    return {
        "users": users_list,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    admin_id: str = Depends(get_current_admin_id),
):
    db = get_db()
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own admin account")

    result = await db.users.update_one({"_id": oid}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "success", "message": "User deactivated successfully", "user_id": user_id, "is_active": False}


@router.patch("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    admin_id: str = Depends(get_current_admin_id),
):
    db = get_db()
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    result = await db.users.update_one({"_id": oid}, {"$set": {"is_active": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "success", "message": "User reactivated successfully", "user_id": user_id, "is_active": True}


# ─────────────────────────────────────────────────────────────
# 5. All Trips List (Searchable & Filterable)
# ─────────────────────────────────────────────────────────────
@router.get("/trips")
async def list_all_trips(
    search: Optional[str] = Query(None, description="Search by destination, from_city, owner name, or owner email"),
    status: Optional[str] = Query(None, description="Filter by status (all | draft | generating | generated | booked)"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    admin_id: str = Depends(get_current_admin_id),
):
    db = get_db()
    pipeline = [
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "owner",
            }
        },
        {"$unwind": {"path": "$owner", "preserveNullAndEmptyArrays": True}},
    ]

    match_conditions = []
    if status and status.lower() != "all":
        match_conditions.append({"status": status.lower()})

    if search and search.strip():
        term = search.strip()
        match_conditions.append({
            "$or": [
                {"destination": {"$regex": term, "$options": "i"}},
                {"from_city": {"$regex": term, "$options": "i"}},
                {"owner.name": {"$regex": term, "$options": "i"}},
                {"owner.email": {"$regex": term, "$options": "i"}},
            ]
        })

    if match_conditions:
        pipeline.append({"$match": {"$and": match_conditions}})

    # Calculate total matching trips
    count_pipeline = list(pipeline)
    count_pipeline.append({"$count": "total"})
    count_result = await db.trips.aggregate(count_pipeline).to_list(length=1)
    total = count_result[0]["total"] if count_result else 0

    pipeline.extend([
        {"$sort": {"created_at": -1}},
        {"$skip": (page - 1) * limit},
        {"$limit": limit},
    ])

    docs = await db.trips.aggregate(pipeline).to_list(length=limit)

    trips_list = []
    for doc in docs:
        owner = doc.get("owner") or {}
        trips_list.append(TripAdminOut(
            id=str(doc["_id"]),
            user_id=str(doc.get("user_id", "")),
            owner_name=owner.get("name", "Unknown"),
            owner_email=owner.get("email", ""),
            destination=doc.get("destination", ""),
            from_city=doc.get("from_city", ""),
            start_date=doc.get("start_date", ""),
            end_date=doc.get("end_date", ""),
            travelers=doc.get("travelers", 1),
            budget=float(doc.get("budget", 0.0)),
            currency=doc.get("currency", "INR"),
            status=doc.get("status", TripStatus.draft),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
        ))

    total_pages = max(1, math.ceil(total / limit))
    return {
        "trips": trips_list,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }
