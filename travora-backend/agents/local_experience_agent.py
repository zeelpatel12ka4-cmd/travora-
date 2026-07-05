"""
Local Experience Agent
Enriches the itinerary with food recommendations, hidden gems,
cultural tips, and local events matched to user interests.
Writes results into context["local_tips"] and enhances context["itinerary"].
"""
from services.llm_client import call_llm, safe_parse_json

SYSTEM_PROMPT = """You are a passionate local travel guide and food critic with insider knowledge
of destinations worldwide. You know the best hidden gems, authentic restaurants, and cultural
experiences that most tourists miss. You match recommendations to traveler interests.
Always respond with valid JSON only — no markdown, no prose outside the JSON object."""

USER_TEMPLATE = """Enhance this trip with local experiences and insider tips:

Destination: {destination}
Travel dates: {start_date} to {end_date}
Travelers: {travelers}
Interests: {interests}
Budget level: {budget_level}

Return a JSON object with exactly these keys:
{{
  "must_eat": [
    {{
      "name": "Dish or restaurant name",
      "description": "What it is and why it's unmissable",
      "price_range": "budget | mid-range | splurge",
      "area": "neighborhood/area"
    }}
  ],
  "hidden_gems": [
    {{
      "name": "Place or experience name",
      "description": "Why it's special and how to get there",
      "best_time": "best time to visit"
    }}
  ],
  "cultural_tips": [
    "Tip 1: specific cultural norm or etiquette",
    "Tip 2",
    "Tip 3"
  ],
  "local_events": "Any notable events, festivals, or seasonal highlights during the travel dates",
  "shopping_tips": "Best places to buy souvenirs and local products",
  "nightlife": "Evening/nightlife options if relevant",
  "day_trips": [
    {{
      "name": "Nearby destination",
      "description": "Why it's worth a day trip",
      "distance": "approximate distance/travel time"
    }}
  ],
  "practical_apps": ["App 1 (purpose)", "App 2 (purpose)"],
  "emergency_info": "Local emergency numbers and nearest hospital area"
}}

Provide at least 5 must_eat items, 3 hidden gems, and 3 day trips."""


class LocalExperienceAgent:
    async def run(self, context: dict) -> dict:
        interests_str = ", ".join(context.get("interests", [])) or "general sightseeing, food, culture"
        budget = context.get("budget", 0)
        budget_level = "budget" if budget < 20000 else ("mid-range" if budget < 75000 else "luxury")

        prompt = USER_TEMPLATE.format(
            destination=context["destination"],
            start_date=context["start_date"],
            end_date=context["end_date"],
            travelers=context["travelers"],
            interests=interests_str,
            budget_level=budget_level,
        )

        try:
            raw = await call_llm(SYSTEM_PROMPT, prompt, max_tokens=3000, temperature=0.8)
            result = safe_parse_json(raw)
        except Exception as e:
            result = {
                "must_eat": [{"name": f"Local {context['destination']} cuisine", "description": "Explore local street food and restaurants.", "price_range": "budget", "area": "city center"}],
                "hidden_gems": [{"name": "Local markets", "description": "Wander through local markets for an authentic experience.", "best_time": "morning"}],
                "cultural_tips": ["Respect local customs and dress codes.", "Learn a few words in the local language.", "Ask locals for restaurant recommendations."],
                "local_events": "Check local tourism websites for current events.",
                "shopping_tips": "Local markets offer the best authentic souvenirs.",
                "nightlife": "Ask hotel concierge for current recommendations.",
                "day_trips": [],
                "practical_apps": ["Google Maps (navigation)", "Google Translate (language)"],
                "emergency_info": "Keep local emergency numbers saved on your phone.",
                "_error": str(e),
            }

        context["local_tips"] = result
        return context
