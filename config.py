import os
from dotenv import load_dotenv
import asyncio
from collections import deque

# Load environment variables
load_dotenv()

# API Configuration
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.0-flash"

# Rate Limiting
MAX_REQUESTS_PER_MINUTE = 15
REQUEST_TIMESTAMPS = deque(maxlen=MAX_REQUESTS_PER_MINUTE)
SEMAPHORE = asyncio.Semaphore(MAX_REQUESTS_PER_MINUTE)
