import ffmpeg
from pathlib import Path
from gemini_upload import upload_file
import asyncio
import concurrent.futures


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
        segments.append((str(output_path), i * segment_length))

    return segments


async def upload_and_process(segment_path):
    """Uploads a video segment to Gemini and returns its file object."""
    file_obj = upload_file(segment_path)
    return (segment_path, file_obj) if file_obj else (segment_path, None)


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
