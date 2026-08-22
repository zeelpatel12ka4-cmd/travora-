"""
Automated Test Suite for Travora Admin Features
Tests all 6 admin features and security constraints using AsyncMongoMockClient.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from bson import ObjectId

# Ensure backend directory in sys.path
sys.path.insert(0, os.path.dirname(__file__))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import database.mongo as mongo_module
from mongomock_motor import AsyncMongoMockClient
from services.auth_service import hash_password, create_access_token
import httpx
from main import app

async def run_admin_tests():
    print("\n" + "="*60)
    print("STARTING TRAVORA ADMIN DASHBOARD TEST SUITE")
    print("="*60)

    # Set up mock DB
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["travora_test"]
    mongo_module.db = mock_db
    mongo_module.client = mock_client

    db = mock_db
    now = datetime.now(timezone.utc)

    # 1. Create regular user
    regular_user = {
        "name": "Regular Traveler",
        "email": "regular@test.com",
        "password_hash": hash_password("Password123!"),
        "is_admin": False,
        "is_active": True,
        "created_at": now,
        "preferences": {"interests": ["Culture", "Food"], "home_city": "Mumbai"},
    }
    reg_res = await db.users.insert_one(regular_user)
    regular_user_id = str(reg_res.inserted_id)

    # 2. Create admin user
    admin_user = {
        "name": "Admin Superuser",
        "email": "admin@test.com",
        "password_hash": hash_password("AdminPass123!"),
        "is_admin": True,
        "is_active": True,
        "created_at": now,
        "preferences": {"interests": ["Luxury", "Beaches"], "home_city": "Delhi"},
    }
    admin_res = await db.users.insert_one(admin_user)
    admin_user_id = str(admin_res.inserted_id)

    # 3. Create test trips
    trip1 = {
        "user_id": ObjectId(regular_user_id),
        "destination": "Goa",
        "from_city": "Mumbai",
        "start_date": "2026-09-01",
        "end_date": "2026-09-05",
        "travelers": 2,
        "budget": 35000.0,
        "currency": "INR",
        "interests": ["Beaches", "Nightlife", "Seafood"],
        "status": "generated",
        "itinerary": [{"day": 1, "title": "Day 1 in Goa", "activities": []}],
        "budget_breakdown": {"total": 35000.0},
        "created_at": now,
        "updated_at": now,
    }
    trip2 = {
        "user_id": ObjectId(regular_user_id),
        "destination": "Goa",
        "from_city": "Bangalore",
        "start_date": "2026-09-10",
        "end_date": "2026-09-14",
        "travelers": 4,
        "budget": 60000.0,
        "currency": "INR",
        "interests": ["Beaches", "Water Sports"],
        "status": "booked",
        "itinerary": [],
        "budget_breakdown": {"total": 60000.0},
        "created_at": now - timedelta(days=2),
        "updated_at": now,
    }
    trip3 = {
        "user_id": ObjectId(admin_user_id),
        "destination": "Paris",
        "from_city": "Delhi",
        "start_date": "2026-10-01",
        "end_date": "2026-10-07",
        "travelers": 2,
        "budget": 250000.0,
        "currency": "INR",
        "interests": ["Art", "Culture", "Romance", "Food"],
        "status": "draft",
        "itinerary": [],
        "budget_breakdown": {"total": 250000.0},
        "created_at": now - timedelta(days=5),
        "updated_at": now,
    }
    trip1_res = await db.trips.insert_one(trip1)
    trip2_res = await db.trips.insert_one(trip2)
    trip3_res = await db.trips.insert_one(trip3)
    trip1_id = str(trip1_res.inserted_id)

    # JWT Tokens
    regular_token = create_access_token({"sub": regular_user_id})
    admin_token = create_access_token({"sub": admin_user_id})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # TEST 1: Security - Non-admin access to admin routes must return 403 Forbidden
        print("\n[Test 1] Security & RBAC Access Control")
        res = await client.get("/api/admin/stats/overview", headers={"Authorization": f"Bearer {regular_token}"})
        assert res.status_code == 403, f"Expected 403 Forbidden for regular user, got {res.status_code}"
        print("  -> Regular user received 403 Forbidden on /api/admin/stats/overview: PASS")

        res_no_auth = await client.get("/api/admin/stats/overview")
        assert res_no_auth.status_code in (401, 403), f"Expected 401/403 for unauthenticated, got {res_no_auth.status_code}"
        print("  -> Unauthenticated user rejected on /api/admin/stats/overview: PASS")

        # TEST 2: Feature 1 - Overview Stats
        print("\n[Test 2] Feature 1 — Overview Stats")
        res = await client.get("/api/admin/stats/overview", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["total_users"] == 2, f"Expected 2 total users, got {data['total_users']}"
        assert data["total_trips"] == 3, f"Expected 3 total trips, got {data['total_trips']}"
        assert data["trips_this_week"] == 3
        assert data["trips_this_month"] == 3
        assert data["generated_trips"] == 1
        assert data["booked_trips"] == 1
        assert data["draft_trips"] == 1
        print(f"  -> Stats: total_users={data['total_users']}, total_trips={data['total_trips']}, generated={data['generated_trips']}, booked={data['booked_trips']}: PASS")

        # TEST 3: Feature 2 - Top Destinations
        print("\n[Test 3] Feature 2 — Top Destinations")
        res = await client.get("/api/admin/stats/top-destinations", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
        dest_data = res.json()
        assert isinstance(dest_data, list)
        top_dest = next((d for d in dest_data if d["destination"] == "Goa"), None)
        assert top_dest is not None and top_dest["trip_count"] == 2, f"Expected 2 trips for Goa, got {top_dest}"
        print(f"  -> Top Destinations grouped accurately. Goa count={top_dest['trip_count']}: PASS")

        # TEST 4: Feature 3 - Top Interests
        print("\n[Test 4] Feature 3 — Top Interests")
        res = await client.get("/api/admin/stats/top-interests", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
        interests_data = res.json()
        assert isinstance(interests_data, list)
        beaches = next((i for i in interests_data if i["interest"] == "Beaches"), None)
        assert beaches is not None and beaches["count"] == 2
        print(f"  -> Top Interests unwound and counted. Beaches tag count={beaches['count']}: PASS")

        # TEST 5: Feature 6 - 30-Day Engagement Chart
        print("\n[Test 5] Feature 6 — 30-Day Engagement Timeline")
        res = await client.get("/api/admin/stats/engagement", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
        eng_data = res.json()
        assert isinstance(eng_data, list) and len(eng_data) == 30, f"Expected 30 daily entries, got {len(eng_data)}"
        total_in_30_days = sum(d["count"] for d in eng_data)
        assert total_in_30_days == 3
        print(f"  -> Engagement returned full 30-day timeline with 3 total trips: PASS")

        # TEST 6: Feature 4 - User List, Search & Soft Deactivation
        print("\n[Test 6] Feature 4 — User Management & Soft Deactivation")
        res = await client.get("/api/admin/users?search=Regular", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
        user_list_data = res.json()
        assert "users" in user_list_data and len(user_list_data["users"]) == 1
        reg_user_item = user_list_data["users"][0]
        assert reg_user_item["id"] == regular_user_id
        assert reg_user_item["trip_count"] == 2, f"Expected 2 trips for regular user, got {reg_user_item['trip_count']}"
        assert reg_user_item["is_active"] is True
        print(f"  -> User list search returned correct user with trip_count={reg_user_item['trip_count']}: PASS")

        # Deactivate regular user
        deact_res = await client.patch(f"/api/admin/users/{regular_user_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
        assert deact_res.status_code == 200, f"Expected 200 on deactivate, got {deact_res.status_code}"
        assert deact_res.json()["is_active"] is False

        # Verify regular user cannot log in when deactivated
        login_res = await client.post("/api/auth/login", json={"email": "regular@test.com", "password": "Password123!"})
        assert login_res.status_code == 403, f"Expected 403 Forbidden for deactivated user login, got {login_res.status_code}"
        print("  -> Deactivated user is blocked from logging in (HTTP 403): PASS")

        # Reactivate regular user
        react_res = await client.patch(f"/api/admin/users/{regular_user_id}/reactivate", headers={"Authorization": f"Bearer {admin_token}"})
        assert react_res.status_code == 200
        assert react_res.json()["is_active"] is True
        print("  -> User reactivated successfully: PASS")

        # TEST 7: Feature 5 - All Trips List & Read-only View
        print("\n[Test 7] Feature 5 — All-Trips List & Read-only Detail View")
        res = await client.get("/api/admin/trips", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
        trip_list_data = res.json()
        assert "trips" in trip_list_data and len(trip_list_data["trips"]) == 3
        first_trip = trip_list_data["trips"][0]
        assert "owner_name" in first_trip and "owner_email" in first_trip
        print(f"  -> Trips list returned all platform trips with owner info (owner='{first_trip['owner_name']}'): PASS")

        # Test Status Filter
        res_filter = await client.get("/api/admin/trips?status=booked", headers={"Authorization": f"Bearer {admin_token}"})
        assert res_filter.status_code == 200
        assert len(res_filter.json()["trips"]) == 1
        assert res_filter.json()["trips"][0]["destination"] == "Goa"
        print("  -> Status filter returned only booked trip: PASS")

        # Test Admin viewing regular user's trip via GET /api/trips/{trip_id}
        view_res = await client.get(f"/api/trips/{trip1_id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert view_res.status_code == 200, f"Expected admin to view regular user trip, got {view_res.status_code}"
        assert view_res.json()["id"] == trip1_id
        print("  -> Admin successfully accessed regular user's itinerary: PASS")

    print("\n" + "="*60)
    print("ALL 7 TEST PHASES PASSED WITH ZERO ERRORS!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_admin_tests())
