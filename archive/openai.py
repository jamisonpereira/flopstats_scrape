import os
import cv2
import math
import datetime
import archive.openai as openai
import io
import json
import base64
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Get values from the environment
api_key = os.getenv("OPENAI_API_KEY")
org_id = os.getenv("OPENAI_ORG_ID")
project_id = os.getenv("OPENAI_PROJECT_ID")

# # Initialize the OpenAI client with the new interface
# client = openai.OpenAI(
#     organization="org-P1AuSJNeMU4W4BF8bOMWwnre",
#     project="proj_UxJaNwUthzbSIonz16H8u41C",
# )

# Initialize the OpenAI client
client = openai.OpenAI(
    api_key=api_key,
    organization=org_id,
    project=project_id,
)


class ImageAnalysisResponse(BaseModel):
    injured: bool = Field(
        ...,
        description="Indicates whether there is obviously an injured player or not.",
    )
    player_name: Optional[str] = Field(
        None, description="The name of the injured player, if identifiable."
    )
    player_team_name: Optional[str] = Field(
        None, description="The team name of the injured player, if identifiable."
    )


# Paths and parameters
VIDEO_PATH = "videos/2024IpsChe_1st trim.mp4"  # Path to your input video file
INJURED_DIR = "injured_frames"  # Directory to save flagged frames
SKIP_SECONDS = 0  # Skip the first X minutes (X00 seconds)
ANALYSIS_INTERVAL = 3  # Analyze one frame every 3 seconds
TARGET_WIDTH = 640  # Resize images to this width for cost efficiency


# Ensure the output directory exists
os.makedirs(INJURED_DIR, exist_ok=True)


def resize_image(frame, target_width=TARGET_WIDTH):
    """
    Resizes the given frame to the target width while maintaining aspect ratio.
    """
    height, width = frame.shape[:2]
    scaling_factor = target_width / float(width)
    new_dimensions = (target_width, int(height * scaling_factor))
    print(f"Resizing image from ({width}x{height}) to {new_dimensions}")
    resized_frame = cv2.resize(frame, new_dimensions, interpolation=cv2.INTER_AREA)
    return resized_frame


def analyze_frame_in_memory(frame, game_timestamp):
    """
    Resizes the frame, overlays the game timestamp, encodes it to JPEG in memory,
    and sends it along with a text prompt to the OpenAI vision model.

    The prompt asks the model to analyze the image to determine if a player
    is on the ground injured (i.e., flopping). The expected JSON output contains:
      - injured (boolean)
      - player_name (string)
      - team (string)
      - game_timestamp (string)

    Returns a dictionary with the analysis result.
    """
    print("Starting analysis of current frame...")
    # Resize the frame for cost efficiency
    # frame_resized = resize_image(frame)

    # Overlay the game timestamp onto the resized frame
    # cv2.putText(
    #     frame_resized,
    #     game_timestamp,
    #     (10, 30),
    #     cv2.FONT_HERSHEY_SIMPLEX,
    #     1,
    #     (0, 255, 0),
    #     2,
    #     cv2.LINE_AA,
    # )
    # print(f"Timestamp '{game_timestamp}' overlayed on frame.")

    # Encode the resized image to JPEG in memory (adjust quality if needed)
    success, encoded_image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        print("Error: Failed to encode image to JPEG format.")
        return None
    print("Image successfully encoded to JPEG in memory.")

    image_bytes = encoded_image.tobytes()

    # Convert the image bytes to a Base64-encoded string
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    print("Image successfully encoded to Base64.")

    # Prepare the prompt for analysis
    prompt = (
        f"Analyze the image to determine if a player is on the ground injured (flopping). "
        "Return a JSON object with keys 'injured' (boolean), 'player_name' (string), 'team' (string), "
        "and 'game_timestamp' (string). Do NOT return any extra text before or after the JSON response."
    )
    # print("Prepared prompt for OpenAI API:")
    # print(prompt)

    try:
        print("Calling OpenAI API for analysis...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Adjust the model name as needed
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            response_format={"type": "json"},
            temperature=1,
            max_completion_tokens=2048,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        print("API call successful. Processing response...")
        result_text = response.choices[0].message.content
        print("Raw API response:", result_text)

        # Convert response from string to JSON
        analysis = (
            json.loads(result_text) if isinstance(result_text, str) else result_text
        )
        print("Parsed analysis result:", analysis)
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        analysis = {
            "injured": False,
            "player_name": "",
            "team": "",
            "game_timestamp": game_timestamp,
        }

    return analysis


def extract_and_process_frames(video_path):
    """
    Opens the video, skips the first SKIP_SECONDS, and then processes one frame every ANALYSIS_INTERVAL.
    Each processed frame is analyzed, and if flagged as containing an injured (flopping) player,
    it is saved to the INJURED_DIR.
    """
    print(f"Opening video file: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video file.")
        return

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / fps
    print(
        f"Video opened successfully: FPS={fps}, Total Frames={total_frames}, Duration={video_duration:.2f} seconds"
    )

    # Skip the first SKIP_SECONDS of the video
    start_frame = math.floor(SKIP_SECONDS * fps)
    print(f"Skipping first {SKIP_SECONDS} seconds, starting at frame {start_frame}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    # Calculate the frame interval based on ANALYSIS_INTERVAL seconds
    frame_interval = math.floor(ANALYSIS_INTERVAL * fps)
    current_frame_index = start_frame

    while current_frame_index < total_frames:
        print(f"\nProcessing frame at index: {current_frame_index}")
        # Set the capture to the current frame index and read the frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_index)
        ret, frame = cap.read()
        if not ret:
            print("No frame returned; ending processing.")
            break

        # Compute the game timestamp for the current frame
        game_seconds = current_frame_index / fps
        game_timestamp = str(datetime.timedelta(seconds=game_seconds))
        print(f"Computed game timestamp: {game_timestamp}")

        # Analyze the frame (processed entirely in memory)
        analysis_result = analyze_frame_in_memory(frame, game_timestamp)
        print(f"Analysis result for frame {current_frame_index}: {analysis_result}")

        # If the model flags an injured (flopping) player, save the frame for review
        if analysis_result and analysis_result.get("injured", False):
            injured_filename = os.path.join(
                INJURED_DIR, f"injured_frame_{current_frame_index:06d}.jpg"
            )
            cv2.imwrite(injured_filename, frame)
            print(f"Flagged injured frame saved as: {injured_filename}")
        else:
            print("No injured player detected in this frame.")

        # Move ahead by the computed frame interval
        current_frame_index += frame_interval
        print(f"Advancing to next frame index: {current_frame_index}")

    cap.release()
    print("Finished processing video.")


if __name__ == "__main__":
    print("Starting soccer game footage analysis...")
    extract_and_process_frames(VIDEO_PATH)
    print("Analysis complete.")
