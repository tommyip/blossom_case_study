"""RSS feed fetching for startup podcasts."""

from datetime import datetime, timedelta, timezone

import feedparser

FEEDS = [
    ("The Pitch", "https://feeds.megaphone.fm/thepitch"),
    ("Twenty Minute VC", "https://feeds.megaphone.fm/WWO3519750118"),
    ("Product Market Fit Show", "https://rss.buzzsprout.com/1889238.rss"),
    ("Indie Hackers", "https://feeds.transistor.fm/the-indie-hackers-podcast"),
    ("My First Million", "https://feeds.megaphone.fm/HS2300184645"),
    ("How I Built This", "https://rss.art19.com/how-i-built-this"),
    ("This Week in Startups", "https://anchor.fm/s/7c624c84/podcast/rss"),
    ("The Full Ratchet", "https://anchor.fm/s/7c624c84/podcast/rss"),
    ("Equity", "https://feeds.megaphone.fm/YFL6537156961"),
    ("Startup Savant", "https://feeds.simplecast.com/y_IjPwmW"),
]


def _parse_date(entry) -> datetime | None:
    """Parse published date from feed entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return None


def fetch_feed(name: str, url: str, cutoff: datetime) -> list[dict]:
    """Fetch episodes from a single RSS feed."""
    try:
        feed = feedparser.parse(url)
        episodes = []
        for entry in feed.entries:
            pub_date = _parse_date(entry)
            if not pub_date or pub_date < cutoff:
                continue
            episodes.append({
                "podcast": name,
                "title": entry.get("title", ""),
                "description": entry.get("summary", ""),
                "pub_date": pub_date.isoformat(),
                "link": entry.get("link", ""),
            })
        return episodes
    except Exception as e:
        print(f"  Failed to fetch {name}: {e}")
        return []


def fetch_all_feeds(days: int = 90) -> list[dict]:
    """Fetch episodes from all feeds within time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    all_episodes = []

    for name, url in FEEDS:
        print(f"  Fetching {name}...")
        episodes = fetch_feed(name, url, cutoff)
        all_episodes.extend(episodes)
        print(f"    {len(episodes)} episodes")

    return all_episodes
