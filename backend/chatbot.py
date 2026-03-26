"""
Smart Parking System v2.0 — AI Chatbot Engine

Intent-based chatbot that responds with real-time data.
Supports 10 intents: availability, best time, compare, price,
predict, book, my bookings, cancel, payment, help.

No external LLM — local pattern matching + database queries.
"""

import re
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    get_all_locations, get_location, get_status,
    get_all_statuses, get_zones_for_location,
    create_booking, get_user_bookings, cancel_booking,
    calculate_parking_fee, save_chat_message,
    get_latest_prediction
)
from backend.ml_engine import (
    find_best_time, detect_peak_hours, run_zone_prediction
)
from backend.config import DB_PATH, LOCATIONS


# ═══════════════════════════════════════════════════════════
# LOCATION NAME MATCHING
# ═══════════════════════════════════════════════════════════

# Map common keywords to location IDs
_LOCATION_KEYWORDS = {
    "mall": "LOC_MALL",
    "elante": "LOC_MALL",
    "shopping": "LOC_MALL",
    "airport": "LOC_AIRPORT",
    "delhi": "LOC_AIRPORT",
    "igi": "LOC_AIRPORT",
    "flight": "LOC_AIRPORT",
    "corporate": "LOC_CORP",
    "infosys": "LOC_CORP",
    "office": "LOC_CORP",
    "tech park": "LOC_CORP",
    "university": "LOC_UNI",
    "campus": "LOC_UNI",
    "college": "LOC_UNI",
    "cu": "LOC_UNI",
    "hospital": "LOC_HOSP",
    "pgimer": "LOC_HOSP",
    "pgi": "LOC_HOSP",
    "medical": "LOC_HOSP",
}

_LOCATION_NAMES = {
    "LOC_MALL": "Elante Mall",
    "LOC_AIRPORT": "Delhi Airport T3",
    "LOC_CORP": "Infosys Tech Park",
    "LOC_UNI": "Chandigarh University",
    "LOC_HOSP": "PGIMER Hospital",
}


def _extract_location(query: str) -> str | None:
    """Extracts location_id from user query using keyword matching."""
    query_lower = query.lower()
    for keyword, loc_id in _LOCATION_KEYWORDS.items():
        if keyword in query_lower:
            return loc_id
    return None


def _extract_hour(query: str) -> int | None:
    """Extracts hour from query like '7 PM', '14:00', '3pm'."""
    # Match patterns like "7 PM", "7PM", "7 pm"
    match = re.search(r'(\d{1,2})\s*(am|pm|AM|PM)', query)
    if match:
        hour = int(match.group(1))
        ampm = match.group(2).lower()
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        return hour

    # Match patterns like "14:00", "at 14"
    match = re.search(r'at\s+(\d{1,2})', query)
    if match:
        return int(match.group(1))

    return None


# ═══════════════════════════════════════════════════════════
# INTENT CLASSIFICATION
# ═══════════════════════════════════════════════════════════

_INTENT_PATTERNS = {
    "CHECK_AVAILABILITY": [
        r'(?:is|are)\s+.+\s+(?:full|empty|available|open)',
        r'how many\s+(?:spots?|slots?|spaces?)',
        r'(?:check|show)\s+(?:availability|status)',
        r'availability',
        r'(?:spots?|slots?|spaces?)\s+(?:at|in|for)',
        r'parking\s+(?:available|full|empty)',
    ],
    "BEST_TIME": [
        r'(?:best|good|ideal|optimal)\s+time',
        r'when\s+(?:should|to)\s+(?:i|we)\s+(?:go|visit|park|come)',
        r'least\s+(?:busy|crowded|full)',
        r'quietest',
    ],
    "COMPARE": [
        r'compare',
        r'which\s+(?:parking|location|lot)\s+(?:is|has)',
        r'(?:least|most)\s+(?:busy|crowded|available|empty)',
        r'(?:all|every)\s+(?:parking|location)',
        r'overview',
    ],
    "PRICE": [
        r'(?:how much|what|price|cost|rate|fee|charge)',
        r'(?:parking|rate)\s+(?:at|for|in)',
        r'per\s+hour',
    ],
    "PREDICT": [
        r'(?:will|would)\s+.+\s+(?:be\s+)?(?:full|busy|crowded|empty)',
        r'predict(?:ion)?',
        r'forecast',
        r'(?:tomorrow|tonight|later|evening|morning)',
    ],
    "BOOK": [
        r'book(?:ing)?',
        r'reserve',
        r'hold\s+(?:a\s+)?(?:spot|slot|space)',
    ],
    "MY_BOOKINGS": [
        r'my\s+(?:booking|reservation)',
        r'(?:show|list|check)\s+(?:my\s+)?(?:booking|reservation)',
    ],
    "CANCEL": [
        r'cancel',
        r'(?:remove|delete)\s+(?:my\s+)?(?:booking|reservation)',
    ],
    "PAYMENT": [
        r'(?:pay|payment)',
        r'(?:how much|what)\s+(?:did|do)\s+(?:i|we)\s+(?:owe|pay|spend)',
        r'(?:my\s+)?(?:bill|invoice|receipt)',
    ],
    "HELP": [
        r'^help$',
        r'what\s+can\s+you\s+do',
        r'(?:options|features|commands)',
        r'how\s+(?:does|do)\s+(?:this|it)\s+work',
    ],
}


def classify_intent(query: str) -> str:
    """Classifies user query into an intent category."""
    query_lower = query.lower().strip()

    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                return intent

    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════
# RESPONSE GENERATORS (One per Intent)
# ═══════════════════════════════════════════════════════════

def _respond_availability(query: str, db_path: str) -> str:
    """Responds to availability queries with real-time data."""
    loc_id = _extract_location(query)

    if loc_id:
        loc = get_location(db_path, loc_id)
        if not loc:
            return f"Sorry, I couldn't find information for that location."

        name = loc['name']
        total = loc['total_capacity']
        occupied = loc['total_occupied']
        avail = loc['total_available']
        util = loc['utilization_percent']

        status_emoji = "🟢" if util < 60 else ("🟡" if util < 85 else "🔴")

        response = (f"{status_emoji} **{name}**\n"
                     f"Occupancy: {occupied}/{total} ({util}% full)\n"
                     f"Available spots: {avail}\n")

        # Add zone breakdown
        if loc.get('zones'):
            response += "\n**Zone breakdown:**\n"
            for z in loc['zones']:
                z_avail = z.get('available_slots', 0) or 0
                z_util = z.get('utilization_percent', 0) or 0
                z_emoji = "🟢" if z_util < 60 else ("🟡" if z_util < 85 else "🔴")
                response += (f"  {z_emoji} {z['zone_name']}: "
                             f"{z_avail}/{z['max_capacity']} available "
                             f"({z_util}%)\n")

        return response
    else:
        # Show all locations
        locations = get_all_locations(db_path)
        if not locations:
            return "No parking locations found in the system."

        response = "**All Parking Locations:**\n\n"
        for loc in locations:
            util = loc.get('utilization_percent', 0)
            avail = loc.get('total_available', 0)
            emoji = "🟢" if util < 60 else ("🟡" if util < 85 else "🔴")
            response += (f"{emoji} **{loc['name']}** ({loc['location_type']})\n"
                         f"   Available: {avail}/{loc['total_capacity']} | "
                         f"Utilization: {util}%\n\n")
        return response


def _respond_best_time(query: str, db_path: str) -> str:
    """Finds the best time to visit a specific location."""
    loc_id = _extract_location(query)
    if not loc_id:
        return ("Please specify a location! For example: "
                "'When is the best time to visit the mall?'")

    loc = get_location(db_path, loc_id)
    if not loc or not loc.get('zones'):
        return "Couldn't find that location."

    response = f"**Best times to park at {loc['name']}:**\n\n"
    for zone in loc['zones']:
        best = find_best_time(zone['zone_id'], db_path)
        peaks = detect_peak_hours(zone['zone_id'], db_path)
        response += (f"📍 **{zone['zone_name']}**\n"
                     f"  Best time: {best['best_hour']} "
                     f"(~{best['expected_occupancy']:.0f} vehicles)\n"
                     f"  Avoid: {peaks['peak_start']} - {peaks['peak_end']} "
                     f"(busiest)\n\n")

    return response


def _respond_compare(query: str, db_path: str) -> str:
    """Compares all locations by availability."""
    locations = get_all_locations(db_path)
    if not locations:
        return "No locations in the system."

    # Sort by utilization (least busy first)
    sorted_locs = sorted(locations, key=lambda x: x.get('utilization_percent', 0))

    response = "**Parking Comparison (sorted by availability):**\n\n"
    for i, loc in enumerate(sorted_locs, 1):
        util = loc.get('utilization_percent', 0)
        avail = loc.get('total_available', 0)
        rate = loc.get('rate_per_hour', 0)
        emoji = "🟢" if util < 60 else ("🟡" if util < 85 else "🔴")

        response += (f"{i}. {emoji} **{loc['name']}**\n"
                     f"   Available: {avail}/{loc['total_capacity']} | "
                     f"{util}% full | Rs.{rate}/hr\n\n")

    best = sorted_locs[0]
    response += (f"💡 **Recommendation:** {best['name']} has the most "
                 f"availability right now.")
    return response


def _respond_price(query: str, db_path: str) -> str:
    """Shows pricing for a location."""
    loc_id = _extract_location(query)
    if not loc_id:
        # Show all prices
        response = "**Parking Rates:**\n\n"
        locations = get_all_locations(db_path)
        for loc in locations:
            rate_hr = loc.get('rate_per_hour', 0)
            rate_day = loc.get('rate_per_day', 0)
            response += (f"📍 **{loc['name']}**\n"
                         f"   Hourly: Rs.{rate_hr} | Daily: Rs.{rate_day}\n\n")
        return response

    fee_1h = calculate_parking_fee(db_path, loc_id, 1)
    fee_3h = calculate_parking_fee(db_path, loc_id, 3)
    fee_8h = calculate_parking_fee(db_path, loc_id, 8)

    name = _LOCATION_NAMES.get(loc_id, loc_id)
    response = (f"**Parking rates at {name}:**\n\n"
                f"  1 hour: Rs.{fee_1h['amount']}\n"
                f"  3 hours: Rs.{fee_3h['amount']}\n"
                f"  8 hours (full day): Rs.{fee_8h['amount']}\n"
                f"  Currency: {fee_1h['currency']}")
    return response


def _respond_predict(query: str, db_path: str) -> str:
    """Predicts future occupancy for a location."""
    loc_id = _extract_location(query)
    hour = _extract_hour(query)

    if not loc_id:
        return ("Please specify a location and time! For example: "
                "'Will the airport be full at 7 PM?'")

    loc = get_location(db_path, loc_id)
    if not loc or not loc.get('zones'):
        return "Couldn't find that location."

    response = f"**Prediction for {loc['name']}**\n\n"

    for zone in loc['zones']:
        pred = get_latest_prediction(db_path, zone['zone_id'])
        if pred:
            pred_count = pred['predicted_count']
            util = round(pred_count / zone['max_capacity'] * 100, 1)
            response += (f"📊 **{zone['zone_name']}**\n"
                         f"  Predicted: {pred_count}/{zone['max_capacity']} "
                         f"({util}% full)\n"
                         f"  Peak hours: {pred['peak_hour_start']} - "
                         f"{pred['peak_hour_end']}\n"
                         f"  Model: {pred.get('model_type', 'N/A')}\n\n")
        else:
            response += f"📊 **{zone['zone_name']}**: No prediction available\n\n"

    if hour is not None:
        response += f"\n⏰ Predicted status at {hour:02d}:00 based on historical patterns."

    return response


def _respond_book(query: str, db_path: str, user_id: int = None) -> str:
    """Guides user through booking."""
    if not user_id:
        return ("Please log in first to book a parking spot. "
                "Go to the **Login** page to create an account or sign in.")

    loc_id = _extract_location(query)
    if not loc_id:
        return ("Which location would you like to book at? "
                "Try: 'Book a spot at the mall' or 'Reserve airport parking'.")

    loc = get_location(db_path, loc_id)
    if not loc:
        return "Couldn't find that location."

    # Find first available zone
    best_zone = None
    for zone in loc.get('zones', []):
        avail = zone.get('available_slots', 0) or 0
        if avail > 0:
            best_zone = zone
            break

    if not best_zone:
        return (f"Sorry, {loc['name']} is currently full. "
                f"Try checking other locations with 'compare parking'.")

    return (f"**Ready to book at {loc['name']}!**\n\n"
            f"Zone: {best_zone['zone_name']}\n"
            f"Available: {best_zone.get('available_slots', 0)} spots\n\n"
            f"To complete your booking, please visit the **Locations** page "
            f"and click **Book Now** on your preferred location.")


def _respond_my_bookings(query: str, db_path: str, user_id: int = None) -> str:
    """Shows user's bookings."""
    if not user_id:
        return "Please log in to view your bookings."

    bookings = get_user_bookings(db_path, user_id)
    if not bookings:
        return "You don't have any bookings yet. Visit the Locations page to book!"

    response = f"**Your Bookings ({len(bookings)}):**\n\n"
    for b in bookings[:10]:
        status_icon = {"CONFIRMED": "✅", "ACTIVE": "🟢",
                       "COMPLETED": "✔️", "CANCELLED": "❌"
                       }.get(b['status'], "❓")
        response += (f"{status_icon} **{b.get('location_name', '')}** - "
                     f"{b.get('zone_name', '')}\n"
                     f"  Status: {b['status']} | "
                     f"Booked: {b['booking_time'][:16]}\n\n")
    return response


def _respond_cancel(query: str, db_path: str, user_id: int = None) -> str:
    """Guides user through cancellation."""
    if not user_id:
        return "Please log in to cancel a booking."

    return ("To cancel a booking, go to your **Profile** page "
            "and click **Cancel** on the booking you want to cancel.\n\n"
            "You can also say 'my bookings' to see all your reservations.")


def _respond_payment(query: str, db_path: str, user_id: int = None) -> str:
    """Shows payment info."""
    if not user_id:
        return "Please log in to view your payment history."

    return ("To view your payment history and receipts, "
            "visit your **Profile** page.\n\n"
            "All payment details including amounts, dates, and "
            "transaction IDs are available there.")


def _respond_help(query: str, db_path: str) -> str:
    """Returns help message with available commands."""
    return (
        "**SmartPark AI Assistant** 🤖\n\n"
        "I can help you with:\n\n"
        "🅿️ **Check availability** — 'Is the mall parking full?'\n"
        "⏰ **Best time to visit** — 'Best time for airport parking?'\n"
        "📊 **Compare locations** — 'Which parking is least busy?'\n"
        "💰 **Check prices** — 'How much is parking at the mall?'\n"
        "🔮 **Predictions** — 'Will the airport be full at 7 PM?'\n"
        "📝 **Book parking** — 'Book a spot at the mall'\n"
        "📋 **My bookings** — 'Show my reservations'\n"
        "❌ **Cancel booking** — 'Cancel my booking'\n"
        "💳 **Payments** — 'My payment history'\n\n"
        "Just type your question naturally!"
    )


def _respond_unknown(query: str, db_path: str) -> str:
    """Graceful fallback for unrecognized queries."""
    return (
        "I'm not sure I understood that. Here are some things I can help with:\n\n"
        "• 'Is the mall full?' (check availability)\n"
        "• 'Best time for airport?' (find best time)\n"
        "• 'Compare parking' (compare all locations)\n"
        "• 'Parking rates' (check prices)\n"
        "• 'Help' (see all options)\n\n"
        "Try asking one of these!"
    )


# ═══════════════════════════════════════════════════════════
# MAIN CHATBOT INTERFACE
# ═══════════════════════════════════════════════════════════

# Intent → Handler mapping
_HANDLERS = {
    "CHECK_AVAILABILITY": _respond_availability,
    "BEST_TIME": _respond_best_time,
    "COMPARE": _respond_compare,
    "PRICE": _respond_price,
    "PREDICT": _respond_predict,
    "HELP": _respond_help,
    "UNKNOWN": _respond_unknown,
}

# Handlers that need user_id
_USER_HANDLERS = {
    "BOOK": _respond_book,
    "MY_BOOKINGS": _respond_my_bookings,
    "CANCEL": _respond_cancel,
    "PAYMENT": _respond_payment,
}


def process_query(query: str, db_path: str = DB_PATH,
                  user_id: int = None) -> dict:
    """Main entry point for chatbot queries.

    Args:
        query: User's natural language question
        db_path: Database path
        user_id: Logged-in user ID (or None for anonymous)

    Returns:
        {intent, response, location_id}
    """
    intent = classify_intent(query)
    location_id = _extract_location(query)

    if intent in _USER_HANDLERS:
        response = _USER_HANDLERS[intent](query, db_path, user_id)
    elif intent in _HANDLERS:
        response = _HANDLERS[intent](query, db_path)
    else:
        response = _respond_unknown(query, db_path)

    # Save to chatbot history
    save_chat_message(db_path, query, response, intent, user_id)

    return {
        "intent": intent,
        "response": response,
        "location_id": location_id
    }


# ═══════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_queries = [
        "Is the mall parking full?",
        "How many spots at the airport?",
        "Best time to visit Elante?",
        "Compare all parking locations",
        "How much is parking at PGIMER?",
        "Will the airport be full at 7 PM?",
        "Book a spot at the office",
        "Help",
        "What is the meaning of life?",
        "Show me availability",
    ]

    print("=" * 70)
    print("  SMART PARKING v2.0 -- Chatbot Verification")
    print("=" * 70)

    for q in test_queries:
        print(f"\n  User: {q}")
        result = process_query(q)
        print(f"  Intent: {result['intent']}")
        # Show first 120 chars of response
        preview = result['response'][:120].replace('\n', ' ')
        print(f"  Bot: {preview}...")
        print("-" * 50)

    print("\n" + "=" * 70)
    print("  [OK] Chatbot verification complete")
    print("=" * 70)
