from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import base64, mimetypes

from database.mongo import get_db
from database.models import (
    UserCreate, UserLogin, UserOut, Token,
    UserPreferences, UserProfile, UserUpdate,
)
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id,
)

router = APIRouter()

# ── Max avatar size: 2 MB ─────────────────────────────────────
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _format_user(doc: dict) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        avatar_url=doc.get("avatar_url", ""),
        created_at=doc["created_at"],
        preferences=UserPreferences(**doc.get("preferences", {})),
        profile=UserProfile(**doc.get("profile", {})),
    )


# ── Signup ────────────────────────────────────────────────────

@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate):
    db = get_db()
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    now = datetime.now(timezone.utc)
    doc = {
        "name":          payload.name,
        "email":         payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "avatar_url":    "",
        "created_at":    now,
        "preferences":   {"interests": [], "home_city": ""},
        "profile": {
            "first_name": "",
            "last_name":  "",
            "phone":      "",
            "city":       "",
            "country":    "",
            "bio":        "",
        },
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id

    user_out = _format_user(doc)
    token = create_access_token({"sub": str(result.inserted_id)})
    return Token(access_token=token, user=user_out)


# ── Login ─────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(payload: UserLogin):
    db = get_db()
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_out = _format_user(doc)
    token = create_access_token({"sub": str(doc["_id"])})
    return Token(access_token=token, user=user_out)


# ── Get current user ─────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def get_me(user_id: str = Depends(get_current_user_id)):
    db = get_db()
    from bson import ObjectId
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return _format_user(doc)


# ── Update profile ────────────────────────────────────────────

@router.put("/me", response_model=UserOut)
async def update_me(payload: UserUpdate, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    from bson import ObjectId

    update_fields = {}
    if payload.name is not None:
        update_fields["name"] = payload.name
    if payload.avatar_url is not None:
        update_fields["avatar_url"] = payload.avatar_url
    if payload.preferences is not None:
        update_fields["preferences"] = payload.preferences.model_dump()
    if payload.profile is not None:
        update_fields["profile"] = payload.profile.model_dump()

    if update_fields:
        await db.users.update_one(
            {"_id": ObjectId(user_id)}, {"$set": update_fields}
        )

    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    return _format_user(doc)


# ── Avatar upload ─────────────────────────────────────────────
# Stores the image as a base64 data-URL in the user document.
# For production, replace with cloud storage (S3 / GCS / Cloudinary).

@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    from bson import ObjectId

    # Validate MIME type
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    content_type = file.content_type or ""
    if content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported image type '{content_type}'. Use JPEG, PNG, WEBP, or GIF.",
        )

    raw = await file.read()
    if len(raw) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar image must be smaller than 2 MB",
        )

    # Encode as data-URL so the browser can use it directly without a CDN
    b64 = base64.b64encode(raw).decode("utf-8")
    data_url = f"data:{content_type};base64,{b64}"

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"avatar_url": data_url}},
    )

    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    return _format_user(doc)
