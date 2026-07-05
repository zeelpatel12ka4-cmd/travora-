"""
Budget Optimizer Agent
Analyses the generated itinerary cost, allocates the budget across categories,
flags overages, and suggests money-saving alternatives.
Writes results into context["budget_breakdown"] and context["budget_notes"].
"""
from services.llm_client import call_llm, safe_parse_json

SYSTEM_PROMPT = """You are a travel budget specialist who helps travelers get the most value from their money.
You analyze trip itineraries, estimate real-world costs, and provide actionable budget advice.
Always respond with valid JSON only — no markdown, no prose outside the JSON object."""

USER_TEMPLATE = """Analyze and optimize the budget for this trip:

Destination: {destination}
From: {from_city}
Dates: {start_date} to {end_date}
Travelers: {travelers}
Total Budget: {budget} {currency}

Itinerary summary (estimated costs per day):
{itinerary_cost_summary}

Return a JSON object with exactly these keys:
{{
  "flights": <estimated round-trip flight cost for all travelers>,
  "hotels": <total accommodation cost for all nights>,
  "food": <total food and dining budget>,
  "activities": <total activities and entrance fees>,
  "transport": <local transport costs>,
  "misc": <miscellaneous (tips, souvenirs, emergencies)>,
  "total": <sum of all above>,
  "within_budget": <true or false>,
  "budget_notes": "2-3 sentences: is the budget sufficient? What's tight?",
  "saving_tips": [
    "Specific tip 1",
    "Specific tip 2",
    "Specific tip 3"
  ],
  "splurge_recommendations": [
    "Worth spending extra on: item/experience"
  ]
}}

All monetary values should be in {currency}. Be realistic with estimates."""


class BudgetAgent:
    async def run(self, context: dict) -> dict:
        itinerary = context.get("itinerary", [])

        # Build a cost summary for the LLM
        cost_lines = []
        for day in itinerary:
            day_cost = day.get("estimated_cost", 0)
            activities = day.get("activities", [])
            activity_names = [a.get("title", "") for a in activities[:3]]
            cost_lines.append(
                f"Day {day.get('day', '?')} ({day.get('title', '')}): "
                f"{context['currency']} {day_cost} — {', '.join(activity_names)}"
            )

        itinerary_cost_summary = "\n".join(cost_lines) if cost_lines else "No itinerary data available"

        prompt = USER_TEMPLATE.format(
            destination=context["destination"],
            from_city=context["from_city"],
            start_date=context["start_date"],
            end_date=context["end_date"],
            travelers=context["travelers"],
            budget=context["budget"],
            currency=context["currency"],
            itinerary_cost_summary=itinerary_cost_summary,
        )

        try:
            raw = await call_llm(SYSTEM_PROMPT, prompt, max_tokens=2048, temperature=0.4)
            result = safe_parse_json(raw)
        except Exception as e:
            # Fallback: simple equal split across categories
            per_category = round(context["budget"] / 5, 2)
            result = {
                "flights": per_category,
                "hotels": per_category,
                "food": per_category,
                "activities": per_category,
                "transport": per_category * 0.5,
                "misc": per_category * 0.5,
                "total": context["budget"],
                "within_budget": True,
                "budget_notes": "Budget estimate generated with fallback method.",
                "saving_tips": ["Book flights early for better rates.", "Consider local guesthouses over hotels.", "Eat at local restaurants for authentic and affordable meals."],
                "splurge_recommendations": ["One special dining experience worth the splurge."],
                "_error": str(e),
            }

        context["budget_breakdown"] = result
        context["budget_notes"] = result.get("budget_notes", "")
        return context
