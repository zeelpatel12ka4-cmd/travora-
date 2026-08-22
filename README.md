# Travora — AI-Powered Travel Planning

> "Your Dream Trip, Planned by AI"

Travora is a full-stack travel planning app powered by a **multi-agent AI system**. Enter a destination, dates, budget, and interests — four specialised AI agents collaborate to generate a personalised, day-by-day itinerary in seconds.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python 3.11+, FastAPI |
| Database | MongoDB (motor async driver) |
| AI | Anthropic Claude / OpenAI (configurable) |
| Auth | JWT (python-jose + passlib/bcrypt) |

---

## Project Structure

```
travora/
├── travora-backend/          # FastAPI backend
│   ├── main.py               # App entrypoint
│   ├── config.py             # Environment config
│   ├── requirements.txt
│   ├── .env.example
│   ├── database/
│   │   ├── mongo.py          # Motor async connection
│   │   └── models.py         # Pydantic schemas
│   ├── routes/
│   │   ├── auth.py           # /api/auth/*
│   │   ├── trips.py          # /api/trips/*
│   │   ├── destinations.py   # /api/destinations/*
│   │   └── planner.py        # /api/planner/*
│   ├── agents/
│   │   ├── orchestrator.py         # Coordinates the pipeline
│   │   ├── research_agent.py       # Destination intelligence
│   │   ├── itinerary_agent.py      # Day-by-day plan builder
│   │   ├── budget_agent.py         # Budget allocation & tips
│   │   └── local_experience_agent.py  # Food, hidden gems, culture
│   └── services/
│       ├── llm_client.py     # Anthropic / OpenAI wrapper
│       └── auth_service.py   # JWT + password hashing
│
└── travora-frontend/         # Static HTML/CSS/JS frontend
    ├── index.html            # Home page
    ├── explore.html          # Destination browser
    ├── planner.html          # AI trip planner (core feature)
    ├── my-trips.html         # Saved itineraries
    ├── trip-detail.html      # Full day-by-day view
    ├── pricing.html
    ├── about.html
    ├── login.html
    ├── signup.html
    ├── css/
    │   ├── style.css         # Global (variables, navbar, footer)
    │   ├── home.css          # Home page styles
    │   └── planner.css       # All inner page styles
    └── js/
        ├── theme.js          # Dark/light mode
        ├── api.js            # Fetch wrapper + utilities
        ├── auth.js           # Auth state + navbar sync
        ├── home.js           # Home page destinations
        ├── planner.js        # Trip planning + itinerary render
        └── trips.js          # My trips + trip detail
```

---

## Quick Start

### 1. Backend

```bash
cd travora-backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
# Edit .env — add your ANTHROPIC_API_KEY and MONGO_URI

# Run the server
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 2. Frontend

Open `travora-frontend/index.html` directly in a browser, **or** use a local server for best results:

```bash
# Using Python (from travora-frontend/)
python -m http.server 5500

# Using VS Code Live Server extension — right-click index.html → Open with Live Server
```

Frontend runs at: http://localhost:5500

### 3. MongoDB

**Option A — Local:**
Install MongoDB Community, start `mongod`. The `MONGO_URI` default (`mongodb://localhost:27017`) will work out of the box.

**Option B — MongoDB Atlas (recommended):**
1. Create a free cluster at https://cloud.mongodb.com
2. Get the connection string and set it as `MONGO_URI` in `.env`

The `destinations` collection is **auto-seeded** with 12 popular destinations on the first API call.

---

## The AI Agent Pipeline

```
User submits trip request
  └─► Orchestrator creates TripContext
        ├─► Step 1: ResearchAgent
        │     Destination overview, weather, visa, safety, transport
        ├─► Step 2: ItineraryAgent (reads research)
        │     Day-by-day plan with activities, timings, costs
        ├─► Step 3: BudgetAgent  ──┐  (run in parallel)
        │     Budget allocation,   │
        │     saving tips          │
        └─► Step 4: LocalAgent  ───┘
              Must-eat, hidden gems, cultural tips
  └─► Orchestrator merges all outputs → saves to MongoDB → returns to frontend
```

---

## Environment Variables

See `travora-backend/.env.example` for all options. Required:

| Variable | Description |
|---|---|
| `MONGO_URI` | MongoDB connection string |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (or use OpenAI) |
| `SECRET_KEY` | Long random string for JWT signing |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/signup` | Register a new user |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Get current user |
| GET | `/api/destinations` | List destinations (filterable) |
| POST | `/api/trips` | Create a trip |
| GET | `/api/trips` | List user's trips |
| GET | `/api/trips/:id` | Get trip detail |
| DELETE | `/api/trips/:id` | Delete a trip |
| POST | `/api/planner/generate` | Run the agent pipeline |
| POST | `/api/planner/regenerate/:id` | Regenerate an existing trip |

---

## Switching LLM Provider

In `.env`:

```env
# Use Anthropic Claude (default)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-sonnet-20241022

# Or use OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o
```

---

## Features

- **Multi-agent AI pipeline** — 4 specialised agents collaborate in parallel
- **Full dark mode** — persisted via localStorage, respects system preference
- **Responsive design** — works on mobile, tablet, and desktop
- **JWT auth** — signup, login, protected routes
- **Trip CRUD** — save, view, delete, regenerate itineraries
- **Budget breakdown** — visual bars with saving tips
- **Local insider tips** — food, hidden gems, cultural etiquette
- **Scroll animations** — fade-up on scroll via IntersectionObserver
- **Destination explorer** — filter by continent, tag, rating, search
