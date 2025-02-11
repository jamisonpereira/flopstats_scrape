import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
from dotenv import load_dotenv
import os
from video_scraper import extract_video_links, initialize_driver, is_driver_alive
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


# Load environment variables from .env file
load_dotenv()


chrome_driver_path = os.getenv("CHROME_DRIVER_PATH")

# Headers to mimic a real browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# List of Footballia match URLs
pages = [
    "https://footballia.eu/matches/tottenham-hotspur-liverpool-fc-premier-league-2024-2025",
    "https://footballia.eu/matches/chelsea-fc-nottingham-forest-premier-league-2024-2025",
    # Add more pages here...
]

# List to store failed scrapes
failed_scrapes = []


def extract_teams(soup, verbose=True):
    """Extracts home team and away team from the correct elements."""
    if verbose:
        print("Extracting teams...")

    # Find all team name elements
    team_elements = soup.find_all("div", class_="team_name m-t")

    if len(team_elements) >= 2:
        home_team = team_elements[0].find("span", itemprop="name").text.strip()
        away_team = team_elements[1].find("span", itemprop="name").text.strip()
    else:
        home_team, away_team = None, None  # Fallback if structure is different

    return home_team, away_team


def extract_league_and_year(soup, verbose=True):
    """Extracts league name and season year separately."""
    if verbose:
        print("Extracting league and year...")

    competition_div = soup.find("div", class_="competition")
    if not competition_div:
        return None, None  # Return None if not found

    # Extract the league name from the <a> tag
    league_name = (
        competition_div.find("a").text.strip() if competition_div.find("a") else None
    )

    # Extract the season year (everything after the <a> tag)
    year_text = (
        competition_div.text.replace(league_name, "").strip() if league_name else None
    )

    return league_name, year_text


def extract_week(soup, verbose=True):
    """Extracts the match week as an integer."""
    if verbose:
        print("Extracting match week...")

    week_div = soup.find("div", class_="stage")
    if not week_div:
        return None  # Return None if the week is missing

    week_text = week_div.text.strip()

    # Extract the number using regex (e.g., "Week 7" → 7)
    match = re.search(r"\d+", week_text)

    return int(match.group()) if match else None  # Convert to integer if found


def extract_location(soup, verbose=True):
    """Extracts the stadium/location."""
    if verbose:
        print("Extracting location...")
    venue_span = soup.find("div", class_="venue").find("span", itemprop="name")
    return venue_span.text.strip() if venue_span else None


def extract_date(soup, verbose=True):
    """Extracts match date and returns separate month (number), day, and year values."""
    if verbose:
        print("Extracting date...")

    date_div = soup.find("div", class_="playing_date")
    if not date_div:
        return None, None, None  # Return None if date is missing

    date_text = date_div.text.strip()

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


def extract_score_and_goals(soup, verbose=True):
    """Extracts match score and goals with player names and minutes by counting goal elements."""
    if verbose:
        print("Extracting score and goals...")
    goals_list = {"home": [], "away": []}

    # Find all goal elements
    goals_div = soup.find("div", class_="goals")
    if not goals_div:
        return 0, 0, goals_list  # No goals found, return 0-0

    goal_divs = goals_div.find_all("div", class_="goal")
    home_score = 0
    away_score = 0

    for goal_div in goal_divs:
        player = goal_div.find("span", title=True).text.strip()
        minute = goal_div.find_all("span")[-1].text.strip()

        if "home" in goal_div.get("class", []):
            goals_list["home"].append({"player": player, "minute": minute})
            home_score += 1  # Count home goal
        else:
            goals_list["away"].append({"player": player, "minute": minute})
            away_score += 1  # Count away goal

    if verbose:
        print(f"Calculated Score: {home_score} - {away_score}")  # Debug print

    return home_score, away_score, goals_list


def extract_players(soup, verbose=True):
    """Extracts player and coach information (country, number, name, age) using table structure."""
    if verbose:
        print("Extracting players and coaches...")
    competitors = {
        "home": {"starters": [], "substitutes": [], "coach": {}},
        "away": {"starters": [], "substitutes": [], "coach": {}},
    }

    players_div = soup.find("div", class_="players")
    if not players_div:
        print("No player data found.")
        return competitors  # Return empty structure if no data is found

    def parse_players(table):
        """Helper function to extract player details from a given <td> table."""
        player_list = []
        if not table:
            return player_list

        rows = table.find_all("tr", class_="player")
        for row in rows:
            try:
                country_tag = row.find("div", class_="flag")
                country = country_tag["title"] if country_tag else "Unknown"

                number_tag = row.find("td", class_="team_number")
                number = number_tag.text.strip() if number_tag else "N/A"

                name_tag = row.find("td", class_="name")
                name = name_tag.text.strip() if name_tag else "Unknown"

                age_tag = row.find("td", class_="age")
                age = age_tag.text.strip() if age_tag else "N/A"

                if "Substitutes" in name:
                    continue

                player_list.append(
                    {"country": country, "number": number, "name": name, "age": age}
                )
            except AttributeError:
                continue  # Skip malformed rows
        return player_list

    def extract_team_tables(row):
        """Helper function to correctly select home and away team tables."""
        team_tds = row.find_all("td", recursive=False)
        if len(team_tds) >= 3:
            home_table = team_tds[0].find("table")
            away_table = team_tds[2].find("table")
            return home_table, away_table
        return None, None

    # Extract Starters
    starters_row = players_div.find("tr", class_="starters")
    if starters_row:
        home_table, away_table = extract_team_tables(starters_row)
        if home_table:
            competitors["home"]["starters"] = parse_players(home_table)
        if away_table:
            competitors["away"]["starters"] = parse_players(away_table)

    # Extract Substitutes
    subs_row = players_div.find("tr", class_="reserves")
    if subs_row:
        home_table, away_table = extract_team_tables(subs_row)
        if home_table:
            competitors["home"]["substitutes"] = parse_players(home_table)
        if away_table:
            competitors["away"]["substitutes"] = parse_players(away_table)

    # Extract Coaches
    coaches_row = players_div.find("tr", class_="coaches")
    if coaches_row:
        home_table, away_table = extract_team_tables(coaches_row)

        def extract_coach(table):
            """Extracts coach information, skipping the first row if needed."""
            if not table:
                return {}
            coach_rows = table.find_all("tr", class_="player")
            if len(coach_rows) < 2:
                return {}

            coach_row = coach_rows[1]  # Skip first row (label) and get second row

            try:
                country_tag = coach_row.find("div", class_="flag")
                country = country_tag["title"] if country_tag else "Unknown"

                name_tag = coach_row.find("td", class_="name")
                name = name_tag.text.strip() if name_tag else "Unknown"

                age_tag = coach_row.find("td", class_="age")
                age = age_tag.text.strip() if age_tag else "N/A"

                return {"name": name, "country": country, "age": age}
            except AttributeError:
                return {}

        if home_table:
            competitors["home"]["coach"] = extract_coach(home_table)
        if away_table:
            competitors["away"]["coach"] = extract_coach(away_table)

    return competitors


def extract_game_data(url, driver, first_open, verbose=True):
    """Extracts all relevant game information from a match page."""
    if verbose:
        print(f"Fetching data from {url}...")

    # Ensure the WebDriver session is still alive
    if not is_driver_alive(driver):
        print("⚠️ WebDriver session lost. Restarting browser...")
        driver.quit()
        driver = initialize_driver(chrome_driver_path)

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch {url}, status code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    game_url = url
    home_team, away_team = extract_teams(soup, verbose)
    league, year = extract_league_and_year(soup, verbose)
    week = extract_week(soup, verbose)
    location = extract_location(soup, verbose)
    month, day, year = extract_date(soup, verbose)
    home_score, away_score, goals = extract_score_and_goals(soup, verbose)
    competitors = extract_players(soup, verbose)
    video_links, video_count = extract_video_links(
        url, driver, chrome_driver_path, first_open, verbose
    )

    game_data = {
        "game_url": game_url,
        "home_team": home_team,
        "away_team": away_team,
        "league": league,
        "year": year,
        "week": week,
        "location": location,
        "date": {"month": month, "day": day, "year": year},
        "score": {"home": home_score, "away": away_score},
        "goals": goals,
        "video_count": video_count,
        "video_links": video_links,
        "competitors": competitors,
    }

    if verbose:
        print(f"Data extracted for {url}")
    return game_data


# Extract data for each match
if __name__ == "__main__":
    games = []
    verbose = False
    first_open = True

    driver = initialize_driver(chrome_driver_path, verbose)
    for page in pages:
        game_info = extract_game_data(page, driver, first_open, verbose)
        if game_info:
            games.append(game_info)
        first_open = False

    with open("match_data.json", "w", encoding="utf-8") as f:
        json.dump(games, f, indent=4, ensure_ascii=False)
