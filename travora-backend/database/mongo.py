import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, MONGO_DB_NAME

client = None
db = None


async def seed_initial_data(database):
    """Seed initial admin and sample data if not already present."""
    from services.auth_service import hash_password

    # 1. Check/seed default admin user
    admin_email = "admin@travora.com"
    existing_admin = await database.users.find_one({"email": admin_email})
    now = datetime.now(timezone.utc)

    if not existing_admin:
        admin_doc = {
            "name": "Zeel Patel (Admin)",
            "email": admin_email,
            "password_hash": hash_password("AdminPassword123"),
            "is_admin": True,
            "is_active": True,
            "created_at": now - timedelta(days=20),
            "preferences": {"interests": ["Luxury", "Culture", "Beaches"], "home_city": "Mumbai"},
        }
        res = await database.users.insert_one(admin_doc)
        admin_id = res.inserted_id
        print(f"[DB] Seeded default admin account: {admin_email} / AdminPassword123")
    else:
        # Ensure is_admin is True
        if not existing_admin.get("is_admin", False):
            await database.users.update_one({"_id": existing_admin["_id"]}, {"$set": {"is_admin": True}})
        admin_id = existing_admin["_id"]

    # 2. Check/seed regular traveler
    traveler_email = "traveler@travora.com"
    existing_traveler = await database.users.find_one({"email": traveler_email})
    if not existing_traveler:
        traveler_doc = {
            "name": "Sarah Jenkins",
            "email": traveler_email,
            "password_hash": hash_password("Traveler123"),
            "is_admin": False,
            "is_active": True,
            "created_at": now - timedelta(days=15),
            "preferences": {"interests": ["Adventure", "Food", "Beaches"], "home_city": "London"},
        }
        res_t = await database.users.insert_one(traveler_doc)
        traveler_id = res_t.inserted_id
        print(f"[DB] Seeded demo traveler account: {traveler_email} / Traveler123")
    else:
        traveler_id = existing_traveler["_id"]

    # 3. Seed sample trips if trips collection is empty
    trips_count = await database.trips.count_documents({})
    if trips_count == 0:
        sample_trips = [
            {
                "user_id": traveler_id,
                "destination": "Goa",
                "from_city": "Mumbai",
                "start_date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
                "travelers": 2,
                "budget": 45000.0,
                "currency": "INR",
                "interests": ["Beaches", "Nightlife", "Seafood"],
                "status": "generated",
                "itinerary": [
                    {
                        "day": 1,
                        "title": "North Goa Beaches & Sunsets",
                        "activities": [
                            {"time": "10:00 AM", "title": "Check-in at Beach Resort", "description": "Relax and unwind at the resort.", "location": "Calangute", "estimated_cost": 5000, "category": "accommodation"},
                            {"time": "04:30 PM", "title": "Sunset at Anjuna Beach", "description": "Enjoy the iconic sunset and beach shacks.", "location": "Anjuna", "estimated_cost": 1500, "category": "attraction"},
                        ],
                        "estimated_cost": 6500.0,
                        "notes": "Rent a scooter for easy travel between beaches.",
                    }
                ],
                "budget_breakdown": {"flights": 12000.0, "hotels": 18000.0, "food": 8000.0, "activities": 5000.0, "transport": 2000.0, "total": 45000.0},
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=2),
            },
            {
                "user_id": traveler_id,
                "destination": "Bali",
                "from_city": "London",
                "start_date": (now + timedelta(days=30)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=38)).strftime("%Y-%m-%d"),
                "travelers": 2,
                "budget": 120000.0,
                "currency": "INR",
                "interests": ["Culture", "Temples", "Beaches", "Food"],
                "status": "booked",
                "itinerary": [],
                "budget_breakdown": {"total": 120000.0},
                "created_at": now - timedelta(days=4),
                "updated_at": now - timedelta(days=4),
            },
            {
                "user_id": admin_id,
                "destination": "Paris",
                "from_city": "Mumbai",
                "start_date": (now + timedelta(days=45)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=52)).strftime("%Y-%m-%d"),
                "travelers": 2,
                "budget": 280000.0,
                "currency": "INR",
                "interests": ["Art", "Romance", "Culture", "Food"],
                "status": "generated",
                "itinerary": [],
                "budget_breakdown": {"total": 280000.0},
                "created_at": now - timedelta(days=1),
                "updated_at": now - timedelta(days=1),
            },
            {
                "user_id": traveler_id,
                "destination": "Tokyo",
                "from_city": "London",
                "start_date": (now + timedelta(days=60)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=70)).strftime("%Y-%m-%d"),
                "travelers": 1,
                "budget": 200000.0,
                "currency": "INR",
                "interests": ["Technology", "Culture", "Food", "Anime"],
                "status": "draft",
                "itinerary": [],
                "budget_breakdown": {"total": 200000.0},
                "created_at": now - timedelta(days=8),
                "updated_at": now - timedelta(days=8),
            },
            {
                "user_id": admin_id,
                "destination": "Dubai",
                "from_city": "Mumbai",
                "start_date": (now + timedelta(days=20)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=25)).strftime("%Y-%m-%d"),
                "travelers": 4,
                "budget": 160000.0,
                "currency": "INR",
                "interests": ["Luxury", "Shopping", "Desert"],
                "status": "booked",
                "itinerary": [],
                "budget_breakdown": {"total": 160000.0},
                "created_at": now - timedelta(days=12),
                "updated_at": now - timedelta(days=12),
            },
            {
                "user_id": traveler_id,
                "destination": "Santorini",
                "from_city": "London",
                "start_date": (now + timedelta(days=50)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=56)).strftime("%Y-%m-%d"),
                "travelers": 2,
                "budget": 190000.0,
                "currency": "INR",
                "interests": ["Romance", "Beaches", "Views"],
                "status": "generated",
                "itinerary": [],
                "budget_breakdown": {"total": 190000.0},
                "created_at": now - timedelta(days=18),
                "updated_at": now - timedelta(days=18),
            },
        ]
        await database.trips.insert_many(sample_trips)
        print(f"[DB] Seeded {len(sample_trips)} sample trips for dashboard analytics")


async def connect_db():
    """Open MongoDB connection with automated fallback if server is offline."""
    global client, db
    try:
        motor_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        # Verify connection with timeout
        await asyncio.wait_for(motor_client.admin.command("ping"), timeout=2.0)
        client = motor_client
        db = client[MONGO_DB_NAME]
        print(f"[DB] Connected to MongoDB — database: '{MONGO_DB_NAME}'")
    except Exception as e:
        print(f"[DB] Local MongoDB daemon not reachable ({e}). Initializing high-fidelity in-memory database.")
        from mongomock_motor import AsyncMongoMockClient
        client = AsyncMongoMockClient()
        db = client[MONGO_DB_NAME]

    await seed_initial_data(db)


async def close_db():
    """Close the connection pool on shutdown."""
    global client
    if client:
        client.close()
        print("[DB] MongoDB connection closed")


def get_db():
    """Return the active database instance."""
    return db
