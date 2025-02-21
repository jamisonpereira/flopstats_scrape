import os
import json
import asyncio
import concurrent.futures
import time
from google import genai
from dotenv import load_dotenv
from pathlib import Path
from gemini_upload import upload_file
from flop_schema import ImageAnalysisResponse
import ffmpeg
from cross_video_flops import handle_cross_video_flops
from pydantic import ValidationError
from collections import deque
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Load environment variables from .env file
load_dotenv()

# Get values from the environment
api_key = os.getenv("GEMINI_API_KEY")

# Initialize client
client = genai.Client(api_key=api_key)
model = "gemini-2.0-flash"
# model = "gemini-2.0-flash-lite"


# API rate limit settings
MAX_REQUESTS_PER_MINUTE = 15
REQUEST_TIMESTAMPS = deque(
    maxlen=MAX_REQUESTS_PER_MINUTE
)  # Tracks last 15 request times
semaphore = asyncio.Semaphore(MAX_REQUESTS_PER_MINUTE)  # Limits concurrency to 15


async def enforce_rate_limit():
    """Ensures we don’t exceed 15 requests per minute."""
    while len(REQUEST_TIMESTAMPS) >= MAX_REQUESTS_PER_MINUTE:
        first_request_time = REQUEST_TIMESTAMPS.popleft()
        time_to_wait = 60 - (time.time() - first_request_time)
        if time_to_wait > 0:
            print(f"Rate limit reached. Waiting {time_to_wait:.2f} seconds...")
            await asyncio.sleep(time_to_wait)


def load_videos(directory="videos"):
    """Loads all video file paths from the specified directory."""
    return [str(f) for f in Path(directory).glob("*.mp4")]


def split_video(video_path, segment_length=30):
    """Splits a video into segments of a specified length (in seconds)."""
    output_dir = Path(video_path).parent / "segments"
    output_dir.mkdir(exist_ok=True)

    segments = []
    probe = ffmpeg.probe(video_path)
    duration = float(probe["format"]["duration"])
    num_segments = int(duration // segment_length) + 1

    for i in range(num_segments):
        output_path = output_dir / f"{Path(video_path).stem}_segment_{i}.mp4"
        ffmpeg.input(video_path, ss=i * segment_length, t=segment_length).output(
            str(output_path), vcodec="copy", acodec="copy"
        ).run(overwrite_output=True, quiet=True)
        segments.append(
            (str(output_path), i * segment_length)
        )  # Store segment path and start time

    return segments


async def upload_and_process(segment_path):
    """Uploads a video segment to Gemini and returns its file object."""
    file_obj = upload_file(segment_path)
    if file_obj:
        return segment_path, file_obj
    else:
        return segment_path, None


async def process_single_video(video_path):
    """Processes a single full game video by segmenting and uploading its segments sequentially."""
    segments = split_video(video_path)

    loop = asyncio.get_event_loop()
    uploaded_files = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        upload_tasks = [
            loop.run_in_executor(executor, upload_and_process, segment[0])
            for segment in segments
        ]
        upload_results = await asyncio.gather(*upload_tasks)

        for (segment_path, segment_start_time), file_obj in zip(
            segments, upload_results
        ):
            if file_obj:
                uploaded_files[segment_path] = (file_obj, segment_start_time)

    return uploaded_files


@retry(
    stop=stop_after_attempt(3),  # Retry up to 3 times
    wait=wait_exponential(
        multiplier=2, min=2, max=10
    ),  # Exponential backoff (2s, 4s, 8s)
    retry=retry_if_exception_type((json.JSONDecodeError, ValidationError, Exception)),
)
async def analyze_segment(segment_path, file_obj, segment_start_time):
    """Runs the Gemini analysis on an uploaded video segment with automatic retries and rate limiting."""
    async with semaphore:  # Limit concurrent requests
        await enforce_rate_limit()  # Ensure we don't exceed the rate limit

        if not file_obj or not file_obj.uri:
            print(f"Skipping analysis for {segment_path}, upload failed.")
            return segment_path, None

        REQUEST_TIMESTAMPS.append(time.time())  # Log request time

        response = client.models.generate_content(
            model=model,
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

                # Adjust timestamps based on segment start time
                for flop_event in validated_data.flops:
                    for player in flop_event.players or []:
                        player.flop_start_video_time += segment_start_time
                        if player.flop_end_video_time is not None:
                            player.flop_end_video_time += segment_start_time

                return segment_path, validated_data.dict()

            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Validation failed for {segment_path}: {e}")
                raise  # `tenacity` will retry the request

    print(f"Max retries reached for {segment_path}. Skipping segment.")
    return segment_path, None


async def analyze_videos(uploaded_files):
    """Processes video segments with rate limiting and retries."""
    results = {}

    tasks = [
        analyze_segment(segment, uploaded_files[segment][0], uploaded_files[segment][1])
        for segment in uploaded_files
    ]

    # Run all analysis tasks with throttling
    batch_results = await asyncio.gather(*tasks)

    for segment_path, result in batch_results:
        if result:
            results[segment_path] = result

    return results


def save_flop_data(flop_data, output_file="flop_data.json"):
    """Saves the processed flop data to a JSON file."""
    with open(output_file, "w") as f:
        json.dump(flop_data, f, indent=4)


async def delete_uploaded_files(uploaded_files):
    """Deletes all uploaded video files from the Gemini file system."""
    for file_obj in uploaded_files.values():
        if file_obj and hasattr(file_obj, "name"):
            try:
                client.files.delete(name=file_obj.name)
                print(f"Deleted file: {file_obj.name}")
            except Exception as e:
                print(f"Failed to delete file {file_obj.name}: {e}")


def main():
    """Main function to coordinate the video processing pipeline."""
    video_files = load_videos()

    if not video_files:
        print("No videos found.")
        return

    loop = asyncio.get_event_loop()
    for video in video_files:
        print(f"Processing video: {video}")
        uploaded_files = loop.run_until_complete(process_single_video(video))
        analysis_results = loop.run_until_complete(analyze_videos(uploaded_files))

        # Save results
        flop_data = [
            json.loads(analysis_results[segment])
            for segment in analysis_results
            if analysis_results[segment]
        ]

        merged_flops = handle_cross_video_flops(flop_data)
        save_flop_data(merged_flops, output_file=f"flop_data_{Path(video).stem}.json")

        # Cleanup uploaded files
        loop.run_until_complete(
            delete_uploaded_files(
                {seg: uploaded_files[seg][0] for seg in uploaded_files}
            )
        )

        print(f"Flop analysis complete for {video}. Results saved and files deleted.")


if __name__ == "__main__":
    main()
