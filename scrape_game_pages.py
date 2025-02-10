import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import time
from dotenv import load_dotenv
import os
from video_scraper import extract_video_links

# Load environment variables from .env file
load_dotenv()

chrome_driver_path = os.getenv("CHROME_DRIVER_PATH")

# Headers to mimic a real browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# List of Footballia match URLs
pages = [
    "https://footballia.eu/matches/chelsea-fc-nottingham-forest-premier-league-2024-2025"
    # Add more pages here...
]


def extract_teams(soup):
    """Extracts home team and away team from the correct elements."""
    print("Extracting teams...")

    # Find all team name elements
    team_elements = soup.find_all("div", class_="team_name m-t")

    if len(team_elements) >= 2:
        home_team = team_elements[0].find("span", itemprop="name").text.strip()
        away_team = team_elements[1].find("span", itemprop="name").text.strip()
    else:
        home_team, away_team = None, None  # Fallback if structure is different

    return home_team, away_team


def extract_league_and_year(soup):
    """Extracts league name and season year separately."""
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


def extract_week(soup):
    """Extracts the match week as an integer."""
    print("Extracting match week...")

    week_div = soup.find("div", class_="stage")
    if not week_div:
        return None  # Return None if the week is missing

    week_text = week_div.text.strip()

    # Extract the number using regex (e.g., "Week 7" → 7)
    match = re.search(r"\d+", week_text)

    return int(match.group()) if match else None  # Convert to integer if found


def extract_location(soup):
    """Extracts the stadium/location."""
    print("Extracting location...")
    venue_span = soup.find("div", class_="venue").find("span", itemprop="name")
    return venue_span.text.strip() if venue_span else None


def extract_date(soup):
    """Extracts match date and returns separate month (number), day, and year values."""
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


def extract_score_and_goals(soup):
    """Extracts match score and goals with player names and minutes by counting goal elements."""
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

    print(f"Calculated Score: {home_score} - {away_score}")  # Debug print

    return home_score, away_score, goals_list


def extract_players(soup):
    """Extracts player and coach information (country, number, name, age) using table structure."""
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


def close_popups(driver):
    """Clicks in the upper-left corner of the viewport to close pop-ups."""
    try:
        print("🛑 Clicking in the upper-left corner to close pop-ups...")

        # Move the mouse to (10, 10) and click
        action = ActionChains(driver)
        action.move_by_offset(10, 10).click().perform()
        time.sleep(0.25)  # Allow UI update

        # Click again in case of multiple pop-ups
        action.move_by_offset(10, 10).click().perform()

        print("✅ Pop-ups dismissed.")

    except Exception as e:
        print(f"⚠️ Could not dismiss pop-ups: {e}")


# Replace with your actual Footballia login credentials
EMAIL = "jamison.pereira@gmail.com"
PASSWORD = "rch7rnt5qfj2wgx.WAH"
USERNAME = "jamison.pereira"


def login_to_footballia(driver):
    """Logs into Footballia using the dropdown login form."""
    print("🔑 Attempting login via dropdown form...")

    # Step 1: Open Footballia's main page
    # driver.get("https://footballia.eu/")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    # Step 2: Click the **SECOND** dropdown toggle button (Sign in)
    try:
        print("📂 Clicking the correct 'Sign in' dropdown toggle...")

        # Find ALL dropdowns
        dropdowns = driver.find_elements(
            By.CSS_SELECTOR, "a.dropdown-toggle[data-toggle='dropdown']"
        )

        if len(dropdowns) > 1:
            sign_in_dropdown = dropdowns[1]  # Select the SECOND dropdown
            sign_in_dropdown.click()
            time.sleep(0.5)  # Give time for dropdown to open
            print("✅ Correct 'Sign in' dropdown opened.")
        else:
            print("⚠️ Could not find the correct dropdown.")
            return

    except Exception as e:
        print(f"⚠️ Unable to click correct dropdown toggle: {e}")
        return

    # Step 3: Wait for the login form inside the dropdown to appear
    try:
        print("🕒 Waiting for login form to appear...")
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "new_user"))
        )
        print("✅ Login form found.")
    except Exception as e:
        print(f"⚠️ Login form did not appear: {e}")
        return

    # Step 4: Fill in login form fields
    print("📝 Filling in login details...")
    email_input = driver.find_element(By.ID, "user_email")
    email_input.clear()
    email_input.send_keys(EMAIL)

    password_input = driver.find_element(By.ID, "user_password")
    password_input.clear()
    password_input.send_keys(PASSWORD)

    # Step 5: Click the login button
    print("🔓 Clicking login button...")
    login_submit = driver.find_element(By.NAME, "commit")
    login_submit.click()

    # Step 6: Wait for login to complete (check for user menu presence)
    try:
        print("🕒 Waiting for username 'jamison.pereira' to appear in the dropdown...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//li[contains(@class, 'dropdown has-panel')]//a[contains(@class, 'dropdown-toggle')]/span[contains(text(), 'jamison.pereira')]",
                )
            )
        )
        print("✅ Login successful. Username found in the dropdown.")
    except Exception as e:
        print(f"⚠️ Login may have failed: {e}")


def click_video_to_start_stream(driver):
    """Clicks the video play button to start streaming."""
    print("🎬 Attempting to start the video stream...")

    try:
        # Step 1: Wait for the video container to be present
        print("🕒 Waiting for video container...")
        video_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "video"))
        )
        print("✅ Video container found.")

        # Step 2: Click the play button inside JW Player
        print("🎬 Clicking the JW Player play button...")
        play_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "jwplayer_display_button"))
        )
        play_button.click()
        time.sleep(3)  # Give time for video to load

        print("✅ Video should now be playing.")

    except Exception as e:
        print(f"⚠️ Unable to start video: {e}")


def check_and_click_next(driver):
    """Checks if the match has two video files, clicks the 'Next' button if needed, and returns True if a second video exists."""
    print("🔍 Checking if the match is divided into two files...")

    try:
        # Step 1: Locate all alert-warning messages
        warnings = driver.find_elements(By.CLASS_NAME, "alert-warning")

        for warning in warnings:
            if "This match is divided in 2 files" in warning.text:
                print("🟡 Match is divided into two files.")

                # Step 2: Locate the "Next" button
                try:
                    print("⏭ Locating the 'Next' button...")
                    next_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".jwnext button")
                        )
                    )
                    print("✅ 'Next' button found.")

                    # # Step 3: Ensure the button is clickable
                    # WebDriverWait(driver, 5).until(
                    #     EC.element_to_be_clickable((By.CSS_SELECTOR, ".jwnext button"))
                    # )

                    # Step 4: Scroll into view to make sure it's interactable
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", next_button
                    )
                    time.sleep(1)  # Allow repositioning

                    # Step 5: Try clicking normally
                    try:
                        print("⏭ Clicking the 'Next' button...")
                        next_button.click()
                        time.sleep(3)  # Allow new video to load
                        print("✅ Successfully clicked 'Next' button.")
                        return True
                    except Exception as click_exception:
                        print(f"⚠️ Normal click failed: {click_exception}")

                        # Step 6: Try JavaScript click as a backup
                        try:
                            print("⏭ Attempting JavaScript click on 'Next' button...")
                            driver.execute_script("arguments[0].click();", next_button)
                            time.sleep(3)
                            print("✅ JavaScript click successful.")
                            return True
                        except Exception as js_e:
                            print(f"❌ JavaScript click also failed: {js_e}")
                            return False

                except Exception as e:
                    print(f"⚠️ Unable to locate 'Next' button: {e}")
                    return False

        print("✅ Match is a single file. No need to click 'Next'.")
        return False

    except Exception as e:
        print(f"❌ Error checking for multiple video files: {e}")
        return False


def extract_video_link_selenium(url):
    """Extracts video link by finding the <video> tag and its 'src' attribute."""
    print(f"Extracting video link from {url} using Selenium...")

    # Configure Selenium
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # Run without opening browser
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Automatically fetch the latest ChromeDriver
    service = Service(chrome_driver_path)  # Update with your chromedriver path
    driver = webdriver.Chrome(service=service, options=chrome_options)

    video_src = []

    try:
        print("🔄 Opening webpage...")
        driver.get(url)

        print("🕒 Sleeping for 5 seconds")
        time.sleep(4)  # Give time for dropdown to open

        close_popups(driver)

        # Step 2: Log in
        login_to_footballia(driver)

        click_video_to_start_stream(driver)

        # Step 3: Wait for the video player to load
        print("🕒 Waiting for <video> tag...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )
        # Step 4: Extract the first video URL
        print("🔍 Extracting first video link...")
        first_video_url = driver.execute_script(
            """
            let video = document.querySelector('video');
            return video ? video.src : null;
            """
        )
        if first_video_url:
            video_src.append(first_video_url)
        time.sleep(1)

        # Step 5: Check for second video and extract its URL
        if check_and_click_next(driver):
            print("🕒 Waiting for the second video to load...")
            time.sleep(5)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )
            print("🔍 Extracting second video link...")
            second_video_url = driver.execute_script(
                """
                let video = document.querySelector('video');
                return video ? video.src : null;
                """
            )
            if second_video_url:
                video_src.append(second_video_url)

        if video_src:
            print(f"🎥 Video Links Found: {video_src}")
            return video_src
        else:
            print("⚠️ No video source found.")
            return None

    except Exception as e:
        print(f"❌ Error extracting video link: {e}")
        return None

    finally:
        print("🔄 Closing browser...")
        # driver.quit()
        print("✅ Selenium session ended.")


def extract_game_data(url):
    """Extracts all relevant game information from a match page."""
    print(f"Fetching data from {url}...")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch {url}, status code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    home_team, away_team = extract_teams(soup)
    league, year = extract_league_and_year(soup)
    week = extract_week(soup)
    location = extract_location(soup)
    month, day, year = extract_date(soup)
    home_score, away_score, goals = extract_score_and_goals(soup)
    competitors = extract_players(soup)
    video_links = extract_video_links(url, chrome_driver_path)
    # video_links = extract_video_link_selenium(url)

    game_data = {
        "home_team": home_team,
        "away_team": away_team,
        "league": league,
        "year": year,
        "week": week,
        "location": location,
        "date": {"month": month, "day": day, "year": year},
        "score": {"home": home_score, "away": away_score},
        "goals": goals,
        "video_links": video_links,
        "competitors": competitors,
    }

    print(f"Data extracted for {url}")
    return game_data


# Extract data for each match
games = []
for page in pages:
    game_info = extract_game_data(page)
    if game_info:
        games.append(game_info)

# Save the data to a JSON file
with open("match_data.json", "w", encoding="utf-8") as f:
    json.dump(games, f, indent=4, ensure_ascii=False)

print("\nExtracted match data saved to 'match_data.json'.")
