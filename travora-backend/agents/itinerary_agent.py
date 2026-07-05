"""
Itinerary Builder Agent
Creates a detailed day-by-day plan: attractions, activities, timing,
travel between locations. Reads research context, writes to context["itinerary"].
"""
from services.llm_client import call_llm, safe_parse_json
from utils.helpers import calculate_trip_days

SYSTEM_PROMPT = """You are an expert travel itinerary planner who creates detailed, realistic,
and enjoyable day-by-day travel plans. You balance must-see highlights with hidden gems.
You consider travel time between locations, opening hours, and pace of travel.
Always respond with valid JSON only — no markdown, no prose outside the JSON array."""

USER_TEMPLATE = """Create a detailed {num_days}-day itinerary for this trip:

Destination: {destination}
Departing from: {from_city}
Dates: {start_date} to {end_date}
Travelers: {travelers}
Budget: {budget} {currency}
Interests: {interests}

Destination research context:
{research_summary}

Return a JSON array where each element is one day:
[
  {{
    "day": 1,
    "date": "YYYY-MM-DD",
    "title": "Catchy day title (e.g., 'Arrival & Beach Vibes')",
    "activities": [
      {{
        "time": "09:00",
        "title": "Activity name",
        "description": "What to do and why it's worth visiting (2-3 sentences)",
        "location": "Specific location name",
        "estimated_cost": 500,
        "category": "attraction | food | transport | accommodation | experience"
      }}
    ],
    "estimated_cost": 3000,
    "notes": "Day-level tip or local insight"
  }}
]

Include 4-6 activities per day. Day 1 should include arrival logistics.
Final day should include departure logistics. Be specific with place names."""


class ItineraryAgent:
    async def run(self, context: dict) -> dict:
        num_days = calculate_trip_days(context["start_date"], context["end_date"])
        research = context.get("research", {})
        research_summary = (
            f"Overview: {research.get('destination_overview', '')}\n"
            f"Weather: {research.get('weather_during_dates', '')}\n"
            f"Top areas: {', '.join(research.get('top_neighborhoods', []))}\n"
            f"Transport: {research.get('local_transport', '')}"
        )
        interests_str = ", ".join(context.get("interests", [])) or "general sightseeing"

        prompt = USER_TEMPLATE.format(
            num_days=num_days,
            destination=context["destination"],
            from_city=context["from_city"],
            start_date=context["start_date"],
            end_date=context["end_date"],
            travelers=context["travelers"],
            budget=context["budget"],
            currency=context["currency"],
            interests=interests_str,
            research_summary=research_summary,
        )

        try:
            raw = await call_llm(SYSTEM_PROMPT, prompt, max_tokens=4096, temperature=0.7)
            result = safe_parse_json(raw)
            if not isinstance(result, list):
                raise ValueError("Expected a JSON array")
        except Exception as e:
            # Fallback: generate a minimal stub itinerary
            result = _stub_itinerary(
                num_days,
                context["destination"],
                context["start_date"],
                str(e),
            )

        context["itinerary"] = result
        return context


def _stub_itinerary(num_days: int, destination: str, start_date: str, error: str) -> list:
    from datetime import date, timedelta
    try:
        base = date.fromisoformat(start_date)
    except Exception:
        base = date.today()

    days = []
    for i in range(num_days):
        day_date = base + timedelta(days=i)
        days.append({
            "day": i + 1,
            "date": day_date.isoformat(),
            "title": f"Day {i + 1} in {destination}",
            "activities": [
                {
                    "time": "09:00",
                    "title": f"Explore {destination}",
                    "description": "Discover the highlights of your destination.",
                    "location": destination,
                    "estimated_cost": 0,
                    "category": "attraction",
                }
            ],
            "estimated_cost": 0,
            "notes": f"Itinerary generation encountered an issue: {error}",
        })
    return days
