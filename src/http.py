from urllib.parse import urlparse
from pathlib import Path
from contextlib import asynccontextmanager

import aiohttp
from aiolimiter import AsyncLimiter
from diskcache import Cache

DATA_DIR = Path(__file__).parent.parent / "data"
cache = Cache(DATA_DIR / ".cache")
TTL = 86400  # 1 day

RATE_LIMITS = {
    "core.cro.ie": AsyncLimiter(1, 1),
    "default": AsyncLimiter(1, 2),
    "indeed.com": AsyncLimiter(2, 1),
    "linkedin.com": AsyncLimiter(2, 1),
    "api.github.com": AsyncLimiter(60, 3600),
}

_session: aiohttp.ClientSession | None = None


def _get_limiter(url: str) -> AsyncLimiter:
    domain = urlparse(url).netloc
    for key, limiter in RATE_LIMITS.items():
        if key in domain:
            return limiter
    return RATE_LIMITS["default"]


async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def fetch(url: str, skip_cache: bool = False) -> str | None:
    if not skip_cache and url in cache:
        return cache[url]

    limiter = _get_limiter(url)
    session = await get_session()

    async with limiter:
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
                cache.set(url, text, expire=TTL)
                return text
        except Exception:
            return None
