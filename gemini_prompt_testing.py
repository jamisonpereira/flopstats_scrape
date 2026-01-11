import os
import json
from dotenv import load_dotenv
from google import genai
from flop_prompt import prompt
from flop_schema import ImageAnalysisResponse

# Load environment variables from .env file
load_dotenv()

# Get values from the environment
api_key = os.getenv("GEMINI_API_KEY")

# Initialize client
client = genai.Client(api_key=api_key)
model = "gemini-2.0-flash"
# model = "gemini-2.0-flash-lite"


def count_tokens(contents):
    return client.models.count_tokens(model=model, contents=contents).total_tokens


def list_files():
    print("My files:")

    for f in client.files.list():
        # Automatically convert the object to a dictionary
        file_data = vars(f)

        # Print JSON-formatted output
        print(
            json.dumps(file_data, indent=2, default=str)
        )  # `default=str` converts non-serializable types like datetime

        # Print a simple name + URI line
        print(f"  {f.name}: {f.uri}\n")


# --- Convert Schema to JSON ---
schema_dict = ImageAnalysisResponse.model_json_schema()
schema_json = json.dumps(schema_dict, indent=2)

list_files()

# --- Select First Uploaded Video File (if available) ---
video_files = client.files.list()
if video_files:
    video_file = video_files[1]  # Take the first uploaded video file
    video_metadata = json.dumps(
        {
            "file_name": video_file.name,
            "file_size_MB": video_file.size_bytes / (1024 * 1024),
            "upload_time": str(video_file.create_time),
        },
        indent=2,
    )
else:
    video_metadata = "{}"  # No video found, use empty JSON

# --- Token Counting ---
prompt_tokens = count_tokens(prompt)
schema_tokens = count_tokens(schema_json)
video_tokens = count_tokens(video_metadata)

total_tokens = prompt_tokens + schema_tokens + video_tokens

# --- Display Token Counts ---
print(f"🔹 Prompt Tokens: {prompt_tokens}")
print(f"🔹 Schema Tokens: {schema_tokens}")
print(f"🔹 Video Metadata Tokens: {video_tokens}")
print(f"🔹 TOTAL Token Count: {total_tokens}")

# --- Count Tokens for Full Request ---
full_request = [video_file, prompt, schema_json, video_metadata]
request_tokens = count_tokens(full_request)

print(f"🟢 Final Request Token Count: {request_tokens}")

# --- Generate Response ---
response = client.models.generate_content(
    model=model,
    contents=[video_file, prompt],
    config={
        "response_mime_type": "application/json",
        "response_schema": list[ImageAnalysisResponse],
    },
)

print("response.text: ", response.text)

# Parse the response using Pydantic
# parsed_response = ImageAnalysisResponse.model_validate_json(response.text)
# print("parsed_response: ", parsed_response)
