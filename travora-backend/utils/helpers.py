from datetime import date


def calculate_trip_days(start_date: str, end_date: str) -> int:
    """Return the number of trip days (inclusive of both ends, min 1)."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        delta = (end - start).days + 1  # inclusive
        return max(delta, 1)
    except (ValueError, TypeError):
        return 1


def build_trip_summary(trip_doc: dict) -> str:
    """Return a one-line text summary of a trip document (for logging/display)."""
    return (
        f"{trip_doc.get('destination', '?')} "
        f"({trip_doc.get('start_date', '?')} – {trip_doc.get('end_date', '?')}) "
        f"× {trip_doc.get('travelers', '?')} travelers, "
        f"budget {trip_doc.get('currency', '')} {trip_doc.get('budget', 0)}"
    )
