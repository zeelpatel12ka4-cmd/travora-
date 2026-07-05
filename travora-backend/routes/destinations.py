from fastapi import APIRouter, Query
from typing import List, Optional
from database.mongo import get_db
from database.models import DestinationOut

router = APIRouter()

# Seed data — inserted on first request if collection is empty
SEED_DESTINATIONS = [
    {"name": "Goa", "country": "India", "continent": "Asia", "tags": ["Beaches", "Nightlife", "Culture"], "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=800", "description": "India's beach paradise with golden sands, vibrant nightlife, and Portuguese heritage.", "popular": True},
    {"name": "Manali", "country": "India", "continent": "Asia", "tags": ["Mountains", "Adventure", "Snow"], "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?w=800", "description": "A Himalayan resort town known for adventure sports and stunning snow-capped peaks.", "popular": True},
    {"name": "Bali", "country": "Indonesia", "continent": "Asia", "tags": ["Beaches", "Culture", "Temples"], "rating": 4.9, "image_url": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=800", "description": "The island of gods — terraced rice fields, ancient temples, and a rich spiritual culture.", "popular": True},
    {"name": "Dubai", "country": "UAE", "continent": "Asia", "tags": ["Luxury", "Shopping", "Modern"], "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800", "description": "A city of superlatives — tallest buildings, largest malls, and world-class dining.", "popular": True},
    {"name": "Bangkok", "country": "Thailand", "continent": "Asia", "tags": ["Culture", "Food", "Temples"], "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1508009603885-50cf7c579365?w=800", "description": "Thailand's vibrant capital with ornate temples, bustling street markets, and street food.", "popular": True},
    {"name": "Santorini", "country": "Greece", "continent": "Europe", "tags": ["Romance", "Beaches", "Views"], "rating": 4.9, "image_url": "https://images.unsplash.com/photo-1613395877344-13d4a8e0d49e?w=800", "description": "Iconic white-washed buildings perched on cliffs above the deep blue Aegean Sea.", "popular": True},
    {"name": "Paris", "country": "France", "continent": "Europe", "tags": ["Romance", "Culture", "Art"], "rating": 4.8, "image_url": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800", "description": "The city of light — the Eiffel Tower, world-class museums, and unmatched cuisine.", "popular": True},
    {"name": "Tokyo", "country": "Japan", "continent": "Asia", "tags": ["Culture", "Food", "Technology"], "rating": 4.9, "image_url": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=800", "description": "A seamless blend of ultra-modern skyscrapers, traditional temples, and incredible food.", "popular": True},
    {"name": "New York", "country": "USA", "continent": "Americas", "tags": ["City", "Culture", "Food"], "rating": 4.7, "image_url": "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?w=800", "description": "The city that never sleeps — iconic skyline, world-famous museums, and endless energy.", "popular": True},
    {"name": "Maldives", "country": "Maldives", "continent": "Asia", "tags": ["Beaches", "Luxury", "Romance"], "rating": 5.0, "image_url": "https://images.unsplash.com/photo-1514282401047-d79a71a590e8?w=800", "description": "Crystal-clear lagoons, overwater bungalows, and pristine coral reefs.", "popular": True},
    {"name": "Rajasthan", "country": "India", "continent": "Asia", "tags": ["Culture", "History", "Desert"], "rating": 4.6, "image_url": "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=800", "description": "The land of kings — majestic forts, colorful festivals, and golden desert landscapes.", "popular": False},
    {"name": "Phuket", "country": "Thailand", "continent": "Asia", "tags": ["Beaches", "Nightlife", "Water Sports"], "rating": 4.5, "image_url": "https://images.unsplash.com/photo-1589394815804-964ed0be2eb5?w=800", "description": "Thailand's largest island with beautiful beaches, clear waters, and vibrant nightlife.", "popular": False},
]


async def seed_destinations(db):
    count = await db.destinations.count_documents({})
    if count == 0:
        await db.destinations.insert_many(SEED_DESTINATIONS)
        print("[DB] Seeded destinations collection")


@router.get("/", response_model=List[DestinationOut])
async def list_destinations(
    popular: Optional[bool] = Query(None, description="Filter by popular flag"),
    continent: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    db = get_db()
    await seed_destinations(db)

    query: dict = {}
    if popular is not None:
        query["popular"] = popular
    if continent:
        query["continent"] = {"$regex": continent, "$options": "i"}
    if tag:
        query["tags"] = {"$in": [tag]}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"country": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]

    cursor = db.destinations.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)

    return [
        DestinationOut(
            id=str(d["_id"]),
            name=d["name"],
            country=d["country"],
            tags=d.get("tags", []),
            rating=d.get("rating", 0.0),
            image_url=d.get("image_url", ""),
            description=d.get("description", ""),
            continent=d.get("continent", ""),
            popular=d.get("popular", False),
        )
        for d in docs
    ]


@router.get("/{destination_id}", response_model=DestinationOut)
async def get_destination(destination_id: str):
    from bson import ObjectId
    from fastapi import HTTPException
    db = get_db()
    try:
        oid = ObjectId(destination_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid destination ID")

    doc = await db.destinations.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Destination not found")

    return DestinationOut(
        id=str(doc["_id"]),
        name=doc["name"],
        country=doc["country"],
        tags=doc.get("tags", []),
        rating=doc.get("rating", 0.0),
        image_url=doc.get("image_url", ""),
        description=doc.get("description", ""),
        continent=doc.get("continent", ""),
        popular=doc.get("popular", False),
    )
