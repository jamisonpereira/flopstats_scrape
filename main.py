import asyncio
from video_processing import load_videos, process_single_video
from analysis import analyze_videos, handle_cross_video_flops
from utils import save_flop_data, delete_uploaded_files
import json


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

        flop_data = [
            json.loads(analysis_results[segment])
            for segment in analysis_results
            if analysis_results[segment]
        ]

        merged_flops = handle_cross_video_flops(flop_data)
        save_flop_data(merged_flops, output_file=f"flop_data_{video}.json")

        loop.run_until_complete(
            delete_uploaded_files(
                {seg: uploaded_files[seg][0] for seg in uploaded_files}
            )
        )

        print(f"Flop analysis complete for {video}. Results saved and files deleted.")


if __name__ == "__main__":
    main()
