import json
import csv
import os
import math
import threading
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from video_scraper import initialize_driver
from scrape_game_pages import extract_game_data
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
chrome_driver_path = os.getenv("CHROME_DRIVER_PATH")

# Lock to prevent race conditions when saving
save_lock = threading.Lock()


def load_matches(file_path, start_date, end_date):
    """Load matches from CSV file within the specified date range."""
    matches = []
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_date = datetime.strptime(row["Playing Date"], "%B %d, %Y")
            if start_date <= match_date <= end_date:
                matches.append(row)
    return matches


def scrape_match_batch(matches, file_name, save_interval=10):
    """Scrape a batch of matches using a single WebDriver instance and save periodically."""
    driver = initialize_driver(chrome_driver_path, verbose=False)
    scraped_data = []

    try:
        for i, match in enumerate(matches, 1):
            print(f"Scraping match URL: {match['Match URL']}")
            game_data = extract_game_data(
                match["Match URL"], driver, first_open=True, verbose=False
            )

            if game_data:
                scraped_data.append(game_data)

            # Save every `save_interval` matches
            if i % save_interval == 0:
                safe_save_data(scraped_data, file_name)
                scraped_data.clear()  # Clear the local buffer after saving
                print(f"✅ Autosaved after {i} matches in this thread.")

    finally:
        driver.quit()  # Close WebDriver once batch is done

    # Final save for remaining data
    if scraped_data:
        safe_save_data(scraped_data, file_name)
        print(f"🔹 Final save complete for this batch.")


def scrape_matches(matches, file_name, max_threads=5, save_interval=10):
    """Scrape matches using multiple threads with each handling multiple matches."""
    # Split matches into chunks for each thread
    chunk_size = math.ceil(len(matches) / max_threads)
    match_chunks = [
        matches[i : i + chunk_size] for i in range(0, len(matches), chunk_size)
    ]

    with ThreadPoolExecutor(max_threads) as executor:
        futures = {
            executor.submit(scrape_match_batch, chunk, file_name, save_interval): chunk
            for chunk in match_chunks
        }

        for future in tqdm(
            futures, total=len(futures), desc="Scraping Progress", unit="batch"
        ):
            future.result()  # Ensure all threads complete


def safe_save_data(new_data, file_name):
    """Safely append new scraped data to the JSON file with a threading lock."""
    with save_lock:  # Prevent multiple threads from writing at the same time
        existing_data = load_existing_data(file_name)
        existing_data.extend(new_data)  # Append new data

        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)


def load_existing_data(file_name):
    """Load existing data from JSON file if it exists."""
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []  # Handle corrupted file gracefully
    return []


def main():
    print("Scraping match data from Footballia...")
    input_file = "urls/game_urls_2015_2025.csv"
    start_date = datetime(2024, 12, 25)
    end_date = datetime(2024, 12, 26)

    # Set filename based on the first script run
    file_name = (
        f"scrape_output/match_data_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    )

    matches = load_matches(input_file, start_date, end_date)
    print(f"Found {len(matches)} matches to scrape.")

    # Adjust max_threads based on system resources
    scrape_matches(matches, file_name, max_threads=1, save_interval=2)


if __name__ == "__main__":
    print("Starting scrape")
    main()
