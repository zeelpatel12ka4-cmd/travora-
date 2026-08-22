from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone

from database.mongo import get_db
from database.models import UserCreate, UserLogin, UserOut, Token, UserPreferences, UserUpdate
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id,
)

router = APIRouter()


def _format_user(doc: dict) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        is_admin=doc.get("is_admin", False),
        is_active=doc.get("is_active", True),
        created_at=doc["created_at"],
        preferences=UserPreferences(**doc.get("preferences", {})),
    )


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate):
    db = get_db()
    # Check duplicate email
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    now = datetime.now(timezone.utc)
    doc = {
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "is_admin": False,
        "is_active": True,
        "created_at": now,
        "preferences": {"interests": [], "home_city": ""},
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id

    user_out = _format_user(doc)
    token = create_access_token({"sub": str(result.inserted_id)})
    return Token(access_token=token, user=user_out)


@router.post("/login", response_model=Token)
async def login(payload: UserLogin):
    db = get_db()
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    user_out = _format_user(doc)
    token = create_access_token({"sub": str(doc["_id"])})
    return Token(access_token=token, user=user_out)


@router.get("/me", response_model=UserOut)
async def get_me(user_id: str = Depends(get_current_user_id)):
    db = get_db()
    from bson import ObjectId
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return _format_user(doc)


@router.put("/me", response_model=UserOut)
async def update_me(payload: UserUpdate, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    from bson import ObjectId
    update_fields = {}
    if payload.name is not None:
        update_fields["name"] = payload.name
    if payload.preferences is not None:
        update_fields["preferences"] = payload.preferences.model_dump()

    if update_fields:
        await db.users.update_one(
            {"_id": ObjectId(user_id)}, {"$set": update_fields}
        )

    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    return _format_user(doc)
