import requests
from bs4 import BeautifulSoup
import csv
import time
import argparse
from datetime import datetime


def extract_date(date_text):
    """Extracts match date and returns separate month (number), day, and year values."""
    # print("Extracting date...")

    try:
        # Convert text to datetime object
        date_obj = datetime.strptime(
            date_text, "%B %d, %Y"
        )  # Example: "October 06, 2024"

        # Extract components
        month = date_obj.month  # Month as integer (1-12)
        day = date_obj.day  # Day as integer (e.g., 6)
        year = date_obj.year  # Year as integer (e.g., 2024)

        return month, day, year
    except ValueError:
        print(f"Error parsing date: {date_text}")
        return None, None, None  # Return None values if parsing fails


def scrape_footballia(start_page, end_page, output_file="matches.csv"):
    base_url = "https://footballia.eu/competitions/premier-league?page="
    matches = []

    for page in range(start_page, end_page - 1, -1):  # Iterating down
        url = f"{base_url}{page}"
        print(f"Scraping {url}...")
        response = requests.get(url)

        if response.status_code != 200:
            print(f"Failed to fetch page {page}, skipping...")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="table-search")

        if not table:
            print(f"No table found on page {page}")
            continue

        rows = table.find("tbody").find_all("tr")

        for row in rows:
            columns = row.find_all("td")
            playing_date = columns[0].text.strip()
            month, day, year = extract_date(playing_date)
            match_link = columns[1].find("a")["href"]
            teams = columns[1].find_all("span", itemprop="name")
            home_team = teams[0].text.strip()
            away_team = teams[1].text.strip()
            competition = columns[2].text.strip()
            stage = columns[3].text.strip()
            season = columns[4].text.strip()
            match_url = "https://footballia.eu" + match_link

            matches.append(
                [
                    playing_date,
                    month,
                    day,
                    year,
                    home_team,
                    away_team,
                    competition,
                    stage,
                    season,
                    match_url,
                ]
            )

        time.sleep(1)  # Politeness delay to avoid overloading the server

    # Save to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Playing Date",
                "Month",
                "Day",
                "Year",
                "Home Team",
                "Away Team",
                "Competition",
                "Stage",
                "Season",
                "Match URL",
            ]
        )
        writer.writerows(matches)

    print(f"Scraping complete. Data saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape match data from Footballia.")
    parser.add_argument("start_page", type=int, help="Starting page number")
    parser.add_argument("end_page", type=int, help="Ending page number")
    parser.add_argument(
        "--output", type=str, default="matches.csv", help="Output CSV file name"
    )
    args = parser.parse_args()

    scrape_footballia(args.start_page, args.end_page, args.output)
