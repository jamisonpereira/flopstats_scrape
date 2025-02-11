import json
import csv
from datetime import datetime
from tqdm import tqdm
from video_scraper import initialize_driver
from scrape_game_pages import extract_game_data
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
chrome_driver_path = os.getenv("CHROME_DRIVER_PATH")


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


def scrape_matches(matches, file_name, save_interval=5):
    """Scrape matches using Selenium and save periodically."""
    driver = initialize_driver(chrome_driver_path, verbose=False)
    scraped_data = load_existing_data(file_name)
    first_open = True

    for i, match in enumerate(tqdm(matches, desc="Scraping Progress", unit="match")):
        print(f"Scraping match URL: {match['Match URL']}")
        game_data = extract_game_data(
            match["Match URL"], driver, first_open, verbose=False
        )
        if game_data:
            scraped_data.append(game_data)

        if (i + 1) % save_interval == 0:
            save_data(scraped_data, file_name)
        first_open = False

    driver.quit()
    save_data(scraped_data, file_name)
    print(f"Scraping complete. Data saved to {file_name}.")


def load_existing_data(file_name):
    """Load existing data from JSON file if it exists."""
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []  # Handle case where file exists but is corrupted
    return []


def save_data(data, file_name):
    """Save scraped data to a JSON file, ensuring previous data is kept."""
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def main():
    print("Scraping match data from Footballia...")
    input_file = "urls/game_urls_2015_2025.csv"
    start_date = datetime(2024, 12, 25)
    end_date = datetime(2024, 12, 26)

    # Set filename based on first script run
    file_name = (
        f"scrape_output/match_data_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    )

    matches = load_matches(input_file, start_date, end_date)
    print(f"Found {len(matches)} matches to scrape.")
    scrape_matches(matches, file_name, save_interval=1)


if __name__ == "__main__":
    print("Starting scrape")
    main()
