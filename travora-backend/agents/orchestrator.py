"""
Orchestrator Agent
Coordinates the full multi-agent pipeline:
  1. ResearchAgent       → destination intelligence
  2. ItineraryAgent      → day-by-day plan
  3. BudgetAgent         → budget allocation & optimization  (can run in parallel with step 4)
  4. LocalExperienceAgent → food, hidden gems, cultural tips (can run in parallel with step 3)
  5. Merge & finalise    → combine into a clean output dict

Maintains a shared TripContext dict throughout the pipeline.
"""
import asyncio
from typing import Optional

from agents.research_agent import ResearchAgent
from agents.itinerary_agent import ItineraryAgent
from agents.budget_agent import BudgetAgent
from agents.local_experience_agent import LocalExperienceAgent


class Orchestrator:
    def __init__(self):
        self.research_agent = ResearchAgent()
        self.itinerary_agent = ItineraryAgent()
        self.budget_agent = BudgetAgent()
        self.local_agent = LocalExperienceAgent()

    async def run(
        self,
        destination: str,
        from_city: str,
        start_date: str,
        end_date: str,
        travelers: int,
        budget: float,
        currency: str = "INR",
        interests: Optional[list] = None,
    ) -> dict:
        """
        Execute the full planning pipeline and return a merged result dict.
        """
        # ── Initialise shared context ────────────────────────────────────────
        context = {
            "destination": destination,
            "from_city": from_city,
            "start_date": start_date,
            "end_date": end_date,
            "travelers": travelers,
            "budget": budget,
            "currency": currency,
            "interests": interests or [],
            # Agent outputs — populated below
            "research": {},
            "itinerary": [],
            "budget_breakdown": {},
            "local_tips": {},
        }

        # ── Step 1: Research (must run first — itinerary depends on it) ──────
        print("[Orchestrator] Step 1/4 — ResearchAgent starting...")
        context = await self.research_agent.run(context)
        print("[Orchestrator] Step 1/4 — ResearchAgent complete")

        # ── Step 2: Build itinerary (depends on research) ────────────────────
        print("[Orchestrator] Step 2/4 — ItineraryAgent starting...")
        context = await self.itinerary_agent.run(context)
        print("[Orchestrator] Step 2/4 — ItineraryAgent complete")

        # ── Steps 3 & 4: Budget + Local Experience in parallel ────────────────
        print("[Orchestrator] Steps 3 & 4 — BudgetAgent + LocalExperienceAgent (parallel)...")
        context_budget, context_local = await asyncio.gather(
            self.budget_agent.run(dict(context)),
            self.local_agent.run(dict(context)),
        )
        # Merge parallel results back into main context
        context["budget_breakdown"] = context_budget.get("budget_breakdown", {})
        context["budget_notes"] = context_budget.get("budget_notes", "")
        context["local_tips"] = context_local.get("local_tips", {})
        print("[Orchestrator] Steps 3 & 4 — complete")

        # ── Finalise & return clean output ────────────────────────────────────
        return self._merge_output(context)

    def _merge_output(self, context: dict) -> dict:
        """Combine all agent outputs into the final result structure."""
        research = context.get("research", {})
        budget = context.get("budget_breakdown", {})
        local = context.get("local_tips", {})

        return {
            "itinerary": context.get("itinerary", []),
            "budget_breakdown": {
                "flights": budget.get("flights", 0),
                "hotels": budget.get("hotels", 0),
                "food": budget.get("food", 0),
                "activities": budget.get("activities", 0),
                "transport": budget.get("transport", 0),
                "misc": budget.get("misc", 0),
                "total": budget.get("total", 0),
                "within_budget": budget.get("within_budget", True),
                "saving_tips": budget.get("saving_tips", []),
                "splurge_recommendations": budget.get("splurge_recommendations", []),
            },
            "agent_notes": {
                "research": research.get("destination_overview", ""),
                "local_tips": _summarise_local(local),
                "budget_notes": context.get("budget_notes", ""),
                "weather": research.get("weather_during_dates", ""),
                "visa": research.get("visa_requirements", ""),
                "safety": research.get("safety_notes", ""),
                "language": research.get("language_tips", ""),
                "currency_notes": research.get("currency_notes", ""),
            },
            "local_tips": local,
            "research": research,
        }


def _summarise_local(local: dict) -> str:
    tips = local.get("cultural_tips", [])
    must_eat = local.get("must_eat", [])
    summary_parts = []
    if must_eat:
        names = [m.get("name", "") for m in must_eat[:3]]
        summary_parts.append(f"Must-eat: {', '.join(names)}")
    if tips:
        summary_parts.append(tips[0] if isinstance(tips[0], str) else str(tips[0]))
    return " | ".join(summary_parts) if summary_parts else ""
