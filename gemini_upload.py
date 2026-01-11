import os
import re
from dotenv import load_dotenv
from google import genai
import time
import ffmpeg
import io

# Load environment variables from .env file
load_dotenv()

# Get values from the environment
api_key = os.getenv("GEMINI_API_KEY")

# Ensure API key is set
if not api_key:
    raise ValueError("GEMINI_API_KEY is not set in the environment variables.")

# Initialize GenAI client
client = genai.Client(api_key=api_key)


def sanitize_filename(filename):
    """
    Sanitizes the filename to comply with Google's naming rules:
    - Only lowercase letters, numbers, and dashes (-) allowed
    - Cannot start or end with a dash
    - Removes invalid characters (like spaces, underscores, dots)
    """
    # Convert to lowercase
    filename = filename.lower()

    # Replace invalid characters with dashes
    filename = re.sub(r"[^a-z0-9-]", "-", filename)

    # Remove leading/trailing dashes
    filename = filename.strip("-")

    # Ensure it has at least one valid character
    if not filename:
        filename = "uploaded-file"

    return filename


def upload_file(file_path):
    """
    Uploads a file to the GenAI API with error handling and duration logging.

    :param file_path: Path to the file to upload
    :return: File object representing the uploaded file, or None if upload failed
    """

    # Check if the file exists before attempting upload
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Extract and sanitize the filename
    original_name = os.path.basename(file_path)
    safe_name = sanitize_filename(original_name)

    print(f"Uploading file: {original_name}...")

    # Start timing the upload
    upload_start_time = time.time()

    try:
        video_file = client.files.upload(
            file=file_path,
            config={
                "name": f"files/{safe_name}",  # Ensure valid name format
                "display_name": original_name,  # Readable name in UI
            },
        )
    except Exception as e:
        print(f"Error during upload: {e}")
        return None

    # Calculate upload duration
    upload_duration = time.time() - upload_start_time
    print(f"Upload completed in {upload_duration:.2f} seconds.")

    # Start timing processing
    processing_start_time = time.time()

    # Monitor the processing status
    try:
        while video_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(1)
            video_file = client.files.get(name=video_file.name)

        # Calculate processing duration
        processing_duration = time.time() - processing_start_time

        if video_file.state.name == "FAILED":
            print("\nFile upload failed during processing.")
            return None

        print(f"\nProcessing completed in {processing_duration:.2f} seconds.")
        print(
            f"Total upload + processing time: {(upload_duration + processing_duration):.2f} seconds."
        )

        return video_file

    except Exception as e:
        print(f"Error checking upload status: {e}")
        return None


def remove_audio(video_path: str) -> str:
    """
    Takes a video file, removes the audio, and saves the processed video to the same directory.

    :param video_path: Path to the input video file.
    :return: Path to the output video file without audio.
    """
    output_path = os.path.splitext(video_path)[0] + "_no_audio.mp4"

    process = (
        ffmpeg.input(video_path)
        .output(
            output_path, vcodec="copy", an=None, movflags="frag_keyframe+empty_moov"
        )
        .run_async(pipe_stdout=True, pipe_stderr=True)
    )

    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    return output_path


# Example usage
video_file = upload_file("videos/2024IpsChe_1st trim (2nd).mp4")

if video_file:
    print(f"Uploaded file name: {video_file}")
else:
    print("File upload failed.")
