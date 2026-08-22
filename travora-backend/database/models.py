from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

class PyObjectId(str):
    """Simple string wrapper so Pydantic accepts MongoDB ObjectIds."""
    pass


# ─────────────────────────────────────────────
# User models
# ─────────────────────────────────────────────

class UserPreferences(BaseModel):
    interests: List[str] = []
    home_city: str = ""


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime
    preferences: UserPreferences = UserPreferences()


class UserAdminOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    trip_count: int = 0
    is_active: bool = True
    is_admin: bool = False


class UserUpdate(BaseModel):
    name: Optional[str] = None
    preferences: Optional[UserPreferences] = None


# ─────────────────────────────────────────────
# Auth models
# ─────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenData(BaseModel):
    user_id: Optional[str] = None


# ─────────────────────────────────────────────
# Trip models
# ─────────────────────────────────────────────

class TripStatus(str, Enum):
    draft = "draft"
    generating = "generating"
    generated = "generated"
    booked = "booked"


class DayActivity(BaseModel):
    time: str = ""
    title: str
    description: str = ""
    location: str = ""
    estimated_cost: float = 0.0
    category: str = ""  # attraction | food | transport | accommodation


class ItineraryDay(BaseModel):
    day: int
    date: Optional[str] = None
    title: str
    activities: List[DayActivity] = []
    estimated_cost: float = 0.0
    notes: str = ""


class BudgetBreakdown(BaseModel):
    flights: float = 0.0
    hotels: float = 0.0
    food: float = 0.0
    activities: float = 0.0
    misc: float = 0.0
    total: float = 0.0


class AgentNotes(BaseModel):
    research: str = ""
    local_tips: str = ""
    budget_notes: str = ""


class TripCreate(BaseModel):
    destination: str = Field(..., min_length=2)
    from_city: str = Field(..., min_length=2)
    start_date: str  # ISO date string YYYY-MM-DD
    end_date: str
    travelers: int = Field(..., ge=1, le=50)
    budget: float = Field(..., gt=0)
    interests: List[str] = []
    currency: str = "INR"


class TripOut(BaseModel):
    id: str
    user_id: str
    destination: str
    from_city: str
    start_date: str
    end_date: str
    travelers: int
    budget: float
    currency: str
    status: TripStatus
    itinerary: List[ItineraryDay] = []
    budget_breakdown: BudgetBreakdown = BudgetBreakdown()
    agent_notes: AgentNotes = AgentNotes()
    created_at: datetime
    updated_at: Optional[datetime] = None


class TripAdminOut(BaseModel):
    id: str
    user_id: str
    owner_name: str = ""
    owner_email: str = ""
    destination: str
    from_city: str
    start_date: str
    end_date: str
    travelers: int
    budget: float
    currency: str = "INR"
    status: TripStatus
    created_at: datetime


class TripUpdate(BaseModel):
    destination: Optional[str] = None
    from_city: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    travelers: Optional[int] = None
    budget: Optional[float] = None
    interests: Optional[List[str]] = None
    status: Optional[TripStatus] = None


# ─────────────────────────────────────────────
# Destination models
# ─────────────────────────────────────────────

class DestinationOut(BaseModel):
    id: str
    name: str
    country: str
    tags: List[str] = []
    rating: float = 0.0
    image_url: str = ""
    description: str = ""
    continent: str = ""
    popular: bool = False


# ─────────────────────────────────────────────
# Planner request model
# ─────────────────────────────────────────────

class PlannerRequest(BaseModel):
    destination: str
    from_city: str
    start_date: str
    end_date: str
    travelers: int = Field(..., ge=1)
    budget: float = Field(..., gt=0)
    currency: str = "INR"
    interests: List[str] = []
    trip_id: Optional[str] = None  # If re-generating an existing trip


class PlannerResponse(BaseModel):
    trip_id: str
    status: str
    message: str
    itinerary: Optional[List[Dict[str, Any]]] = None
    budget_breakdown: Optional[Dict[str, Any]] = None
    agent_notes: Optional[Dict[str, str]] = None
