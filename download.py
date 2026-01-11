import requests
import os
from tqdm import tqdm

def download_video(url, save_path=None, chunk_size=1024 * 1024):
    """
    Downloads a video from the given URL with a progress bar and saves it to the specified path.

    :param url: URL of the video to download
    :param save_path: Local path to save the downloaded video (optional)
    :param chunk_size: Size of chunks to download (default: 1MB)
    """
    try:
        # Send a request to get the file size (some servers may not support this)
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Get file size from headers (if available)
        total_size = int(response.headers.get("content-length", 0))

        # Use the filename from the URL if not provided
        if not save_path:
            save_path = os.path.join(os.getcwd(), url.split("/")[-1])

        # Open the file in write mode and download in chunks
        with open(save_path, "wb") as file, tqdm(
            total=total_size, unit="B", unit_scale=True, desc="Downloading", ascii=True
        ) as progress_bar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:  # Filter out keep-alive chunks
                    file.write(chunk)
                    progress_bar.update(len(chunk))  # Update progress bar

        print(f"Download complete: {save_path}")

    except requests.exceptions.RequestException as e:
        print(f"Error downloading the video: {e}")

# Example usage
video_url = "https://videos.footballia.net/uploads/video/source_file/71033/2024BreNfo_1st.mp4" 
download_video(video_url, "videos/test_video.mp4")  # Optional custom filename
