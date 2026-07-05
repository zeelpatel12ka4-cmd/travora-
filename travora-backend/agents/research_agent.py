"""
Destination Research Agent
Gathers: best time to visit, weather, safety, visa/entry requirements,
         transport options, top neighbourhoods.
Writes results into context["research"].
"""
from services.llm_client import call_llm, safe_parse_json

SYSTEM_PROMPT = """You are an expert travel researcher with encyclopedic knowledge of destinations worldwide.
Your job is to provide concise, accurate, and practical destination intelligence for trip planners.
Always respond with valid JSON only — no markdown, no prose outside the JSON object."""

USER_TEMPLATE = """Research the destination for a traveler planning this trip:

Destination: {destination}
Departing from: {from_city}
Travel dates: {start_date} to {end_date}
Number of travelers: {travelers}
Currency: {currency}

Return a JSON object with exactly these keys:
{{
  "destination_overview": "2-3 sentence summary of the destination",
  "best_time_to_visit": "when to go and why",
  "weather_during_dates": "expected weather for the travel dates",
  "visa_requirements": "visa/entry requirements for travelers from {from_city}",
  "safety_notes": "current safety situation and practical tips",
  "local_transport": "main transport options within the destination",
  "top_neighborhoods": ["area1", "area2", "area3"],
  "language_tips": "key phrases or language notes",
  "currency_notes": "local currency, payment customs, tipping norms",
  "health_notes": "vaccinations, health precautions if relevant"
}}"""


class ResearchAgent:
    async def run(self, context: dict) -> dict:
        prompt = USER_TEMPLATE.format(
            destination=context["destination"],
            from_city=context["from_city"],
            start_date=context["start_date"],
            end_date=context["end_date"],
            travelers=context["travelers"],
            currency=context["currency"],
        )

        try:
            raw = await call_llm(SYSTEM_PROMPT, prompt, max_tokens=2048, temperature=0.5)
            result = safe_parse_json(raw)
        except Exception as e:
            # Graceful degradation — provide minimal stub so pipeline continues
            result = {
                "destination_overview": f"Popular travel destination: {context['destination']}.",
                "best_time_to_visit": "Year-round destination with peak and off-peak seasons.",
                "weather_during_dates": "Check local weather forecast closer to travel dates.",
                "visa_requirements": "Check official embassy website for current visa requirements.",
                "safety_notes": "Exercise normal travel precautions.",
                "local_transport": "Taxi, ride-hailing apps, and public transport available.",
                "top_neighborhoods": [],
                "language_tips": "English widely spoken in tourist areas.",
                "currency_notes": f"Carry local currency and {context['currency']}.",
                "health_notes": "Consult your doctor about recommended vaccinations.",
                "_error": str(e),
            }

        context["research"] = result
        return context
