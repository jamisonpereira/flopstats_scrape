import json
import time
import asyncio
from difflib import SequenceMatcher
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from google import genai
from flop_schema import ImageAnalysisResponse
from pydantic import ValidationError
from config import API_KEY, MODEL, SEMAPHORE, REQUEST_TIMESTAMPS
from rate_limiter import enforce_rate_limit
from utils import map_team_name


client = genai.Client(api_key=API_KEY)

### 🔹 ANALYZE VIDEO SEGMENTS ###


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type((json.JSONDecodeError, ValidationError, Exception)),
)
async def analyze_segment(segment_path, file_obj, segment_start_time):
    """Runs the Gemini analysis on an uploaded video segment with retries and rate limiting."""
    async with SEMAPHORE:
        await enforce_rate_limit()

        if not file_obj or not file_obj.uri:
            print(f"Skipping analysis for {segment_path}, upload failed.")
            return segment_path, None

        REQUEST_TIMESTAMPS.append(time.time())

        response = client.models.generate_content(
            model=MODEL,
            contents=[{"file": file_obj.uri}, "flop_prompt.py"],
            config={
                "response_mime_type": "application/json",
                "response_schema": list[ImageAnalysisResponse],
            },
        )

        if response and response.text:
            try:
                flop_data = json.loads(response.text)
                validated_data = ImageAnalysisResponse(**flop_data)

                for flop_event in validated_data.flops:
                    for player in flop_event.players or []:
                        player.player_team_name = map_team_name(player.player_team_name)

                        # Adjust timestamps based on segment start time
                        player.flop_start_video_time += segment_start_time
                        if player.flop_end_video_time is not None:
                            player.flop_end_video_time += segment_start_time

                return segment_path, validated_data.dict()

            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Validation failed for {segment_path}: {e}")
                raise

    print(f"Max retries reached for {segment_path}. Skipping segment.")
    return segment_path, None


async def analyze_videos(uploaded_files):
    """Processes video segments with retries prioritized over new analyses."""
    retry_queue = asyncio.Queue()  # Queue to hold retry tasks

    async def retry_task(segment, file_obj, start_time):
        """Adds a failed segment to the retry queue."""
        await retry_queue.put((segment, file_obj, start_time))

    # Step 1: Try to analyze all video segments
    tasks = []
    for segment in uploaded_files:
        tasks.append(
            analyze_segment(
                segment, uploaded_files[segment][0], uploaded_files[segment][1]
            )
        )

    # Step 2: Wait for initial batch to complete
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Step 3: Identify failed segments and enqueue them for retry
    for i, result in enumerate(batch_results):
        if isinstance(result, Exception):
            segment = list(uploaded_files.keys())[i]
            file_obj, start_time = uploaded_files[segment]
            await retry_task(segment, file_obj, start_time)

    # Step 4: Process retries before handling new requests
    while not retry_queue.empty():
        segment, file_obj, start_time = await retry_queue.get()
        print(f"Retrying failed segment: {segment}")
        await analyze_segment(segment, file_obj, start_time)

    # Step 5: Return results
    return handle_cross_video_flops(
        {
            segment: result
            for segment, result in zip(uploaded_files, batch_results)
            if result
        }
    )


### 🔹 MERGE OVERLAPPING FLOPS ###


def extract_surname(full_name):
    """Extracts the surname from a player's full name."""
    return full_name.split()[-1] if full_name else ""


def similar(a, b):
    """Returns similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def handle_cross_video_flops(flop_data, time_threshold=3, similarity_threshold=0.7):
    """Merges flops that span across two video segments if they are close in time and involve at least one similar surname."""
    # Step 1: Sort flops by start video time
    flop_data.sort(
        key=lambda flop: min(p["flop_start_video_time"] for p in flop["players"])
    )

    merged_flops = []
    prev_flop = None

    for index, flop_event in enumerate(flop_data):
        if not prev_flop:
            prev_flop = flop_event
            continue

        prev_surnames = {
            extract_surname(p["player_name"])
            for p in prev_flop["players"]
            if p["player_name"]
        }
        current_surnames = {
            extract_surname(p["player_name"])
            for p in flop_event["players"]
            if p["player_name"]
        }

        common_players = any(
            similar(prev, curr) >= similarity_threshold
            for prev in prev_surnames
            for curr in current_surnames
        )

        prev_end_time = max(p["flop_end_video_time"] for p in prev_flop["players"])
        current_start_time = min(
            p["flop_start_video_time"] for p in flop_event["players"]
        )

        if common_players and abs(current_start_time - prev_end_time) <= time_threshold:
            print("\n  ******************")
            print("  Merging two flops!")
            print("  ******************\n")

            # Merge players while ensuring earliest start time and latest end time for each
            player_map = {}
            for player in prev_flop["players"] + flop_event["players"]:
                name = player["player_name"]
                if name in player_map:
                    # Update timestamps
                    player_map[name]["flop_start_video_time"] = min(
                        player_map[name]["flop_start_video_time"],
                        player["flop_start_video_time"],
                    )
                    player_map[name]["flop_end_video_time"] = max(
                        player_map[name]["flop_end_video_time"],
                        player["flop_end_video_time"],
                    )
                    player_map[name]["flop_start_game_time"] = min(
                        player_map[name]["flop_start_game_time"],
                        player["flop_start_game_time"],
                    )
                    player_map[name]["flop_end_game_time"] = max(
                        player_map[name]["flop_end_game_time"],
                        player["flop_end_game_time"],
                    )
                else:
                    # Add new player entry
                    player_map[name] = player

            prev_flop["players"] = list(player_map.values())

            # Deduplicate referee decisions
            prev_flop["referee_decisions"] = list(
                set(prev_flop["referee_decisions"] + flop_event["referee_decisions"])
            )

        else:
            merged_flops.append(prev_flop)
            prev_flop = flop_event

    if prev_flop:
        merged_flops.append(prev_flop)

    return merged_flops
