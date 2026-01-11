import asyncio
import time
from config import MAX_REQUESTS_PER_MINUTE, REQUEST_TIMESTAMPS


async def enforce_rate_limit():
    """Ensures we don’t exceed 15 requests per minute."""
    while len(REQUEST_TIMESTAMPS) >= MAX_REQUESTS_PER_MINUTE:
        first_request_time = REQUEST_TIMESTAMPS.popleft()
        time_to_wait = 60 - (time.time() - first_request_time)
        if time_to_wait > 0:
            print(f"Rate limit reached. Waiting {time_to_wait:.2f} seconds...")
            await asyncio.sleep(time_to_wait)
