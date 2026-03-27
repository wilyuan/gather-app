#!/usr/bin/env python3
"""
Gather — Event Scraper for Kraków & Warsaw
Pulls real activity/event data from multiple sources and pushes to Supabase.

Sources:
  1. Google Places API — hobby shops, studios, sports venues, cafés with events
  2. Meetup.com — public group events via unofficial API
  3. Eventbrite — public events via API

Usage:
  1. Copy .env.example to .env and fill in your keys
  2. pip install -r requirements.txt
  3. python scrape.py --city krakow
  4. python scrape.py --city warsaw
"""

import os
import json
import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ============================================
# CONFIG
# ============================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

CITIES = {
    "krakow": {"name": "Kraków", "lat": 50.0647, "lng": 19.9450, "radius": 8000},
    "warsaw": {"name": "Warsaw", "lat": 52.2297, "lng": 21.0122, "radius": 12000},
}

# Google Places search queries mapped to Gather categories
PLACE_QUERIES = [
    {"query": "board game cafe", "category": "Board Games", "lang_guess": "en_pl"},
    {"query": "gry planszowe", "category": "Board Games", "lang_guess": "pl"},
    {"query": "dance studio salsa bachata", "category": "Dancing", "lang_guess": "en_pl"},
    {"query": "szkoła tańca", "category": "Dancing", "lang_guess": "pl"},
    {"query": "yoga studio", "category": "Yoga & Wellness", "lang_guess": "en_pl"},
    {"query": "climbing gym bouldering", "category": "Sports & Fitness", "lang_guess": "en_pl"},
    {"query": "ścianka wspinaczkowa", "category": "Sports & Fitness", "lang_guess": "pl"},
    {"query": "pottery ceramics workshop", "category": "Art & Craft", "lang_guess": "en"},
    {"query": "cooking class", "category": "Food & Cooking", "lang_guess": "en"},
    {"query": "warsztaty kulinarne", "category": "Food & Cooking", "lang_guess": "pl"},
    {"query": "language exchange cafe", "category": "Language Exchange", "lang_guess": "en_pl"},
    {"query": "photography workshop", "category": "Photography", "lang_guess": "en"},
    {"query": "live music jazz open mic", "category": "Music", "lang_guess": "en_pl"},
    {"query": "klub muzyczny jam session", "category": "Music", "lang_guess": "pl"},
    {"query": "trading card game shop MTG Pokemon", "category": "Trading Cards", "lang_guess": "en_pl"},
    {"query": "sklep z grami karcianymi", "category": "Trading Cards", "lang_guess": "pl"},
    {"query": "running club", "category": "Running", "lang_guess": "en"},
    {"query": "coworking space tech meetup", "category": "Tech & Coding", "lang_guess": "en"},
    {"query": "book club english", "category": "Book Club", "lang_guess": "en"},
    {"query": "kayak canoe rental", "category": "Outdoor & Nature", "lang_guess": "en_pl"},
]

# Meetup search topics
MEETUP_TOPICS = [
    "board-games", "hiking", "language-exchange", "photography",
    "yoga", "dancing", "running", "coding", "book-club",
    "cooking", "music", "art", "outdoor-adventures", "fitness",
]


def get_supabase() -> Client:
    """Initialize Supabase client with service role key (bypasses RLS)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def make_source_id(source: str, external_id: str) -> str:
    """Create a deterministic ID so we can upsert without duplicates."""
    raw = f"{source}:{external_id}"
    return hashlib.md5(raw.encode()).hexdigest()


# ============================================
# GOOGLE PLACES SCRAPER
# ============================================
def scrape_google_places(city_key: str) -> list[dict]:
    """Search Google Places API for hobby/activity venues near a city."""
    if not GOOGLE_API_KEY:
        print("  ⚠️  No GOOGLE_PLACES_API_KEY set, skipping Google Places")
        return []

    city = CITIES[city_key]
    results = []
    seen_place_ids = set()

    print(f"\n📍 Scraping Google Places for {city['name']}...")

    for pq in PLACE_QUERIES:
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": f"{pq['query']} in {city['name']} Poland",
            "location": f"{city['lat']},{city['lng']}",
            "radius": city["radius"],
            "key": GOOGLE_API_KEY,
        }

        try:
            resp = httpx.get(url, params=params, timeout=15)
            data = resp.json()

            if data.get("status") != "OK":
                print(f"  ⚠️  Google Places returned {data.get('status')} for '{pq['query']}'")
                continue

            for place in data.get("results", [])[:5]:  # Top 5 per query
                pid = place["place_id"]
                if pid in seen_place_ids:
                    continue
                seen_place_ids.add(pid)

                loc = place["geometry"]["location"]
                activity = {
                    "source_id": make_source_id("google", pid),
                    "title": place["name"],
                    "description": f"Found on Google Maps. Visit for more info.",
                    "category_name": pq["category"],
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "location_name": place["name"],
                    "address": place.get("formatted_address", ""),
                    "lang": pq["lang_guess"],
                    "source": "scraped_google",
                    "source_url": f"https://www.google.com/maps/place/?q=place_id:{pid}",
                    "is_business": True,
                    "frequency": "weekly",  # Businesses are recurring by nature
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("user_ratings_total", 0),
                }
                results.append(activity)
                print(f"  ✅ {place['name']} ({pq['category']})")

        except Exception as e:
            print(f"  ❌ Error scraping '{pq['query']}': {e}")

    print(f"  Found {len(results)} places from Google")
    return results


# ============================================
# MEETUP SCRAPER
# ============================================
def scrape_meetup(city_key: str) -> list[dict]:
    """Scrape upcoming Meetup events near a city using their public GraphQL endpoint."""
    city = CITIES[city_key]
    results = []

    print(f"\n🤝 Scraping Meetup for {city['name']}...")

    # Meetup's public API endpoint for searching events
    url = "https://www.meetup.com/gql"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }

    for topic in MEETUP_TOPICS:
        query = {
            "operationName": "categorySearch",
            "variables": {
                "first": 10,
                "lat": city["lat"],
                "lon": city["lng"],
                "radius": int(city["radius"] / 1000),  # km
                "startDateRange": datetime.now(timezone.utc).isoformat(),
                "endDateRange": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                "query": topic,
            },
            "query": """
                query categorySearch($first: Int, $lat: Float!, $lon: Float!, $radius: Int,
                    $startDateRange: ZonedDateTime, $endDateRange: ZonedDateTime, $query: String) {
                    rankedEvents(filter: {
                        lat: $lat, lon: $lon, radius: $radius,
                        startDateRange: $startDateRange, endDateRange: $endDateRange,
                        query: $query
                    }, first: $first) {
                        edges {
                            node {
                                id
                                title
                                description
                                dateTime
                                endTime
                                going
                                maxTickets
                                eventUrl
                                venue {
                                    name
                                    address
                                    lat
                                    lng
                                }
                                group {
                                    name
                                }
                            }
                        }
                    }
                }
            """,
        }

        try:
            resp = httpx.post(url, json=query, headers=headers, timeout=15)
            data = resp.json()

            events = data.get("data", {}).get("rankedEvents", {}).get("edges", [])
            for edge in events:
                ev = edge["node"]
                venue = ev.get("venue") or {}

                # Skip if no location data
                if not venue.get("lat") or not venue.get("lng"):
                    continue

                # Guess language from title/description
                lang = guess_language(ev.get("title", "") + " " + (ev.get("description", "") or ""))

                activity = {
                    "source_id": make_source_id("meetup", ev["id"]),
                    "title": ev["title"],
                    "description": clean_html(ev.get("description", "")),
                    "category_name": topic_to_category(topic),
                    "lat": venue["lat"],
                    "lng": venue["lng"],
                    "location_name": venue.get("name", ""),
                    "address": venue.get("address", ""),
                    "starts_at": ev.get("dateTime"),
                    "lang": lang,
                    "source": "scraped_meetup",
                    "source_url": ev.get("eventUrl", ""),
                    "is_business": False,
                    "frequency": "one_time",
                    "participants": ev.get("going", 0),
                    "max_participants": ev.get("maxTickets"),
                    "host_name": ev.get("group", {}).get("name", ""),
                }
                results.append(activity)
                print(f"  ✅ {ev['title'][:60]}... ({topic})")

        except Exception as e:
            print(f"  ❌ Error scraping Meetup topic '{topic}': {e}")

    print(f"  Found {len(results)} events from Meetup")
    return results


# ============================================
# EVENTBRITE SCRAPER
# ============================================
def scrape_eventbrite(city_key: str) -> list[dict]:
    """Scrape public Eventbrite events via their search page."""
    city = CITIES[city_key]
    city_slug = city_key.replace("ó", "o")
    results = []

    print(f"\n🎫 Scraping Eventbrite for {city['name']}...")

    search_terms = [
        "board games", "yoga", "dance", "cooking class", "language exchange",
        "photography", "hiking", "running", "art workshop", "music jam",
        "tech meetup", "book club", "pottery", "climbing",
    ]

    for term in search_terms:
        url = f"https://www.eventbriteapi.com/v3/events/search/"
        # Eventbrite's public search endpoint
        search_url = f"https://www.eventbrite.com/d/poland--{city_slug}/{term.replace(' ', '-')}/"

        try:
            resp = httpx.get(
                search_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                timeout=15,
                follow_redirects=True,
            )

            if resp.status_code != 200:
                continue

            # Parse the server-rendered data from the page
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            # Eventbrite embeds event data in script tags
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld_data = json.loads(script.string)
                    events = ld_data if isinstance(ld_data, list) else [ld_data]

                    for ev in events:
                        if ev.get("@type") != "Event":
                            continue

                        loc = ev.get("location", {})
                        geo = loc.get("geo", {})
                        if not geo.get("latitude") or not geo.get("longitude"):
                            continue

                        lang = guess_language(ev.get("name", "") + " " + ev.get("description", ""))

                        activity = {
                            "source_id": make_source_id("eventbrite", ev.get("url", term)),
                            "title": ev.get("name", ""),
                            "description": ev.get("description", "")[:500],
                            "category_name": term_to_category(term),
                            "lat": float(geo["latitude"]),
                            "lng": float(geo["longitude"]),
                            "location_name": loc.get("name", ""),
                            "address": loc.get("address", {}).get("streetAddress", ""),
                            "starts_at": ev.get("startDate"),
                            "lang": lang,
                            "source": "scraped_eventbrite",
                            "source_url": ev.get("url", ""),
                            "is_business": False,
                            "frequency": "one_time",
                            "host_name": ev.get("organizer", {}).get("name", ""),
                        }
                        results.append(activity)
                        print(f"  ✅ {ev.get('name', '')[:60]}...")

                except (json.JSONDecodeError, KeyError):
                    continue

        except Exception as e:
            print(f"  ❌ Error scraping Eventbrite '{term}': {e}")

    print(f"  Found {len(results)} events from Eventbrite")
    return results


# ============================================
# HELPERS
# ============================================
POLISH_WORDS = {
    "ul.", "plac", "park", "warsztat", "spotkanie", "gra", "zabawa",
    "taniec", "bieg", "spacer", "gotowanie", "malowanie", "język",
    "piwo", "kawiarnia", "klub", "zajęcia", "kurs", "wydarzenie",
    "zapraszamy", "wstęp", "darmowe", "bilety", "zapisy", "sobota",
    "niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek",
}


def guess_language(text: str) -> str:
    """Heuristic: if text contains Polish-specific words/chars, mark as pl or en_pl."""
    text_lower = text.lower()
    polish_chars = any(c in text for c in "ąćęłńóśźż")
    polish_words = sum(1 for w in POLISH_WORDS if w in text_lower)

    has_english = any(w in text_lower for w in ["join", "welcome", "free", "class", "workshop", "meetup", "english"])

    if polish_chars or polish_words >= 2:
        if has_english:
            return "en_pl"
        return "pl"
    return "en"


def clean_html(text: str) -> str:
    """Strip HTML tags from description text."""
    if not text:
        return ""
    from bs4 import BeautifulSoup
    return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)[:500]


TOPIC_CATEGORY_MAP = {
    "board-games": "Board Games",
    "hiking": "Outdoor & Nature",
    "language-exchange": "Language Exchange",
    "photography": "Photography",
    "yoga": "Yoga & Wellness",
    "dancing": "Dancing",
    "running": "Running",
    "coding": "Tech & Coding",
    "book-club": "Book Club",
    "cooking": "Food & Cooking",
    "music": "Music",
    "art": "Art & Craft",
    "outdoor-adventures": "Outdoor & Nature",
    "fitness": "Sports & Fitness",
}

TERM_CATEGORY_MAP = {
    "board games": "Board Games",
    "yoga": "Yoga & Wellness",
    "dance": "Dancing",
    "cooking class": "Food & Cooking",
    "language exchange": "Language Exchange",
    "photography": "Photography",
    "hiking": "Outdoor & Nature",
    "running": "Running",
    "art workshop": "Art & Craft",
    "music jam": "Music",
    "tech meetup": "Tech & Coding",
    "book club": "Book Club",
    "pottery": "Art & Craft",
    "climbing": "Sports & Fitness",
}


def topic_to_category(topic: str) -> str:
    return TOPIC_CATEGORY_MAP.get(topic, "Sports & Fitness")


def term_to_category(term: str) -> str:
    return TERM_CATEGORY_MAP.get(term, "Sports & Fitness")


# ============================================
# PUSH TO SUPABASE
# ============================================
def push_to_supabase(activities: list[dict], city_key: str):
    """Insert or update activities in Supabase."""
    if not activities:
        print("\n⚠️  No activities to push")
        return

    sb = get_supabase()

    # Get city ID
    city_name = CITIES[city_key]["name"]
    city_resp = sb.table("cities").select("id").eq("name", city_name).execute()
    if not city_resp.data:
        print(f"❌ City '{city_name}' not found in database. Run the schema SQL first.")
        return
    city_id = city_resp.data[0]["id"]

    # Get category map
    cat_resp = sb.table("categories").select("id, name").execute()
    cat_map = {c["name"]: c["id"] for c in cat_resp.data}

    # Map language values
    lang_map = {"en": "en", "pl": "pl", "en_pl": "en_pl", "other": "other"}

    inserted = 0
    skipped = 0
    errors = 0

    print(f"\n🚀 Pushing {len(activities)} activities to Supabase...")

    for act in activities:
        try:
            category_id = cat_map.get(act["category_name"])
            if not category_id:
                print(f"  ⚠️  Unknown category '{act['category_name']}', skipping")
                skipped += 1
                continue

            # Default starts_at to next week if not provided (for business venues)
            starts_at = act.get("starts_at")
            if not starts_at:
                next_week = datetime.now(timezone.utc) + timedelta(days=7)
                starts_at = next_week.replace(hour=18, minute=0, second=0).isoformat()

            row = {
                "title": act["title"][:200],
                "description": (act.get("description") or "")[:1000],
                "category_id": category_id,
                "city_id": city_id,
                "lat": act["lat"],
                "lng": act["lng"],
                "location_name": (act.get("location_name") or "")[:200],
                "address": (act.get("address") or "")[:300],
                "starts_at": starts_at,
                "frequency": act.get("frequency", "one_time"),
                "lang": lang_map.get(act.get("lang", "en"), "en"),
                "source": act.get("source", "manual_seed"),
                "source_url": act.get("source_url"),
                "is_business": act.get("is_business", False),
                "max_participants": act.get("max_participants"),
                "status": "active",
            }

            # Upsert based on source + source_url to avoid duplicates
            sb.table("activities").insert(row).execute()
            inserted += 1

        except Exception as e:
            err_msg = str(e)
            if "duplicate" in err_msg.lower() or "unique" in err_msg.lower():
                skipped += 1
            else:
                print(f"  ❌ Error inserting '{act['title'][:40]}': {e}")
                errors += 1

    print(f"\n📊 Results: {inserted} inserted, {skipped} skipped, {errors} errors")


# ============================================
# EXPORT TO JSON (for demo mode / backup)
# ============================================
def export_to_json(activities: list[dict], city_key: str):
    """Save scraped data as JSON file for local testing without Supabase."""
    filename = f"scraped_{city_key}_{datetime.now().strftime('%Y%m%d')}.json"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(activities, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 Saved {len(activities)} activities to {filename}")
    return filepath


# ============================================
# MAIN
# ============================================
def main():
    parser = argparse.ArgumentParser(description="Gather — Event Scraper")
    parser.add_argument("--city", choices=["krakow", "warsaw", "all"], default="krakow",
                        help="City to scrape (default: krakow)")
    parser.add_argument("--sources", nargs="+", choices=["google", "meetup", "eventbrite", "all"],
                        default=["all"], help="Sources to scrape")
    parser.add_argument("--push", action="store_true",
                        help="Push results to Supabase (otherwise just saves JSON)")
    parser.add_argument("--json", action="store_true", default=True,
                        help="Export results to JSON file")
    args = parser.parse_args()

    cities = ["krakow", "warsaw"] if args.city == "all" else [args.city]
    sources = ["google", "meetup", "eventbrite"] if "all" in args.sources else args.sources

    for city in cities:
        print(f"\n{'='*50}")
        print(f"🌍 Scraping {CITIES[city]['name']}")
        print(f"{'='*50}")

        all_activities = []

        if "google" in sources:
            all_activities.extend(scrape_google_places(city))

        if "meetup" in sources:
            all_activities.extend(scrape_meetup(city))

        if "eventbrite" in sources:
            all_activities.extend(scrape_eventbrite(city))

        # Deduplicate by title + location
        seen = set()
        unique = []
        for a in all_activities:
            key = f"{a['title'].lower().strip()}|{a.get('lat',0):.4f}"
            if key not in seen:
                seen.add(key)
                unique.append(a)
        all_activities = unique

        print(f"\n📊 Total unique activities for {CITIES[city]['name']}: {len(all_activities)}")

        if args.json:
            export_to_json(all_activities, city)

        if args.push:
            push_to_supabase(all_activities, city)


if __name__ == "__main__":
    main()
