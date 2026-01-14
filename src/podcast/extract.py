"""Guest extraction from podcast episodes using DeepSeek."""

import asyncio
import json
import os
import re

from openai import AsyncOpenAI

from src.http import cache, TTL

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EXTRACT_MODEL = "deepseek/deepseek-chat-v3-0324"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    return _client


def _build_prompt(episode: dict) -> str:
    """Build extraction prompt from episode info."""
    return f"""Extract guest information from this podcast episode.

Podcast: {episode.get("podcast", "")}
Title: {episode.get("title", "")}
Description: {episode.get("description", "")}

If this episode features a guest founder/executive, extract their information.
If no clear guest is identified (e.g., news roundup, host solo episode), return null values.

Return JSON only, no other text:
{{
    "guest_name": "Full name of guest or null",
    "company_name": "Their company or null",
    "role": "Title (CEO, Founder, CTO, etc.) or null",
    "is_founder": true/false/null
}}"""


def _parse_response(text: str) -> dict | None:
    """Parse JSON from response."""
    # Try to find JSON in response
    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not json_match:
        return None
    try:
        data = json.loads(json_match.group())
        if not data.get("guest_name") or not data.get("company_name"):
            return None
        return data
    except json.JSONDecodeError:
        return None


async def extract_guest(episode: dict) -> dict | None:
    """Extract guest info from episode using DeepSeek."""
    cache_key = f"podcast_extract:{episode.get('podcast')}:{episode.get('title')}"

    if cache_key in cache:
        return cache[cache_key]

    prompt = _build_prompt(episode)

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=EXTRACT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        text = response.choices[0].message.content
        guest = _parse_response(text)

        if guest:
            result = {
                **guest,
                "podcast": episode.get("podcast"),
                "episode_title": episode.get("title"),
                "pub_date": episode.get("pub_date"),
                "link": episode.get("link"),
            }
            cache.set(cache_key, result, expire=TTL)
            return result
        return None

    except Exception as e:
        print(f"    Extract failed: {episode.get('title')[:50]} - {e}")
        return None


async def extract_all_guests(episodes: list[dict], concurrency: int = 20) -> list[dict]:
    """Extract guests from all episodes concurrently."""
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0

    async def limited_extract(ep: dict) -> dict | None:
        nonlocal completed
        async with semaphore:
            result = await extract_guest(ep)
            completed += 1
            if completed % 50 == 0 or completed == len(episodes):
                print(f"    {completed}/{len(episodes)}")
            return result

    results = await asyncio.gather(*[limited_extract(ep) for ep in episodes])
    return [r for r in results if r is not None]
