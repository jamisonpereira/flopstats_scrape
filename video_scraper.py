from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException
import time
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

EMAIL = os.getenv("FOOTBALLIA_EMAIL")
PASSWORD = os.getenv("FOOTBALLIA_PASSWORD")
USERNAME = os.getenv("FOOTBALLIA_USERNAME")


def initialize_driver(chrome_driver_path, verbose=True):
    """Initializes and returns a Selenium WebDriver instance with necessary options."""
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # Run without opening browser
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(chrome_driver_path)
    return webdriver.Chrome(service=service, options=chrome_options)


def is_driver_alive(driver, verbose=True):
    """Check if WebDriver is still active before making new requests."""
    try:
        driver.title  # Access an attribute to test if session is active
        return True
    except WebDriverException:
        return False  # If it fails, WebDriver session is lost


def stop_page_loading(driver, verbose=True):
    """Stops the page from loading further to save bandwidth."""
    driver.execute_script("window.stop();")
    if verbose:
        print("🛑 Page loading stopped.")


def close_popups(driver, verbose=True):
    """Clicks in the upper-left corner of the viewport to close pop-ups."""
    try:
        if verbose:
            print("🛑 Closing pop-ups by clicking in the upper-left corner...")
        action = ActionChains(driver)

        # Move mouse to (1,1), click, then reset cursor to (0,0)
        action.move_by_offset(1, 1).click().perform()
        action.move_by_offset(-1, -1).perform()  # Reset back to (0,0)
        if verbose:
            print("✅ Pop-up dismissed.")
    except Exception as e:
        print(f"⚠️ Could not dismiss pop-ups: {e}")


def login_to_footballia(driver, verbose=True):
    """Logs into Footballia using the dropdown login form, but skips if already logged in."""
    if verbose:
        print("🔑 Checking login status...")

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    # Step 1: Check if already logged in by looking for the username
    try:
        user_element = driver.find_element(
            By.XPATH,
            f"//li[contains(@class, 'dropdown')]//span[contains(text(), '{USERNAME}')]",
        )
        if user_element:
            if verbose:
                print(f"✅ Already logged in as {USERNAME}. Skipping login.")
            time.sleep(0.5)
            return
    except NoSuchElementException:
        if verbose:
            print("🔄 Not logged in. Proceeding with login.")

    # Step 2: Open the login dropdown
    try:
        if verbose:
            print("📂 Clicking the 'Sign in' dropdown toggle...")
        dropdowns = driver.find_elements(
            By.CSS_SELECTOR, "a.dropdown-toggle[data-toggle='dropdown']"
        )
        if len(dropdowns) > 1:
            dropdowns[1].click()
            if verbose:
                print("✅ Sign in dropdown opened.")
            time.sleep(0.25)
        else:
            print("⚠️ Could not find the correct dropdown.")
            return
    except Exception as e:
        print(f"⚠️ Unable to click dropdown: {e}")
        return

    # Step 3: Fill in login form
    try:
        if verbose:
            print("🕒 Waiting for login form...")
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "new_user"))
        )
        if verbose:
            print("✅ Login form found.")

        driver.find_element(By.ID, "user_email").send_keys(EMAIL)
        driver.find_element(By.ID, "user_password").send_keys(PASSWORD)
        time.sleep(0.25)  # Small delay to simulate human input

        if verbose:
            print("🔓 Submitting login form...")

        # Use JavaScript to ensure the login button is clicked properly
        login_button = driver.find_element(By.NAME, "commit")
        driver.execute_script(
            "arguments[0].click();", login_button
        )  # Force JavaScript click

        time.sleep(0.25)  # Short delay before checking for login confirmation

        # print("🔓 Submitting login form...")
        # driver.find_element(By.NAME, "commit").click()

        # Step 4: Confirm login was successful
        if verbose:
            print("🕒 Waiting for confirmation...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    f"//li[contains(@class, 'dropdown')]//span[contains(text(), '{USERNAME}')]",
                )
            )
        )
        if verbose:
            print("✅ Login successful.")
    except Exception as e:
        print(f"⚠️ Login failed: {e}")


def click_video_to_start_stream(driver, verbose=True):
    """Clicks the play button to start the video."""
    if verbose:
        print("🎬 Starting video stream...")

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "video"))
        )
        if verbose:
            print("✅ Video container found.")

        play_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "jwplayer_display_button"))
        )
        play_button.click()
        time.sleep(3)
        if verbose:
            print("✅ Video playing.")
    except Exception as e:
        print(f"⚠️ Video did not start: {e}")


def check_and_click_next(driver, verbose=True):
    """Checks if the match has two videos and clicks the 'Next' button if needed."""
    if verbose:
        print("🔍 Checking for multiple video files...")

    try:
        warnings = driver.find_elements(By.CLASS_NAME, "alert-warning")
        for warning in warnings:
            if "This match is divided in 2 files" in warning.text:
                if verbose:
                    print("🟡 Match has two videos.")

                try:
                    if verbose:
                        print("⏭ Locating 'Next' button...")
                    next_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".jwnext button")
                        )
                    )
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", next_button
                    )
                    # time.sleep(1)

                    try:
                        if verbose:
                            print("⏭ Clicking 'Next' button...")
                        next_button.click()
                        time.sleep(2.5)
                        if verbose:
                            print("✅ Advanced to second video.")
                        return True
                    except:
                        if verbose:
                            print("⚠️ Normal click failed, trying JavaScript click...")
                        driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(2.5)
                        if verbose:
                            print("✅ JavaScript click successful.")
                        return True

                except Exception as e:
                    print(f"⚠️ Could not locate 'Next' button: {e}")
                    return False

        if verbose:
            print("✅ Single video detected.")
        return False
    except Exception as e:
        print(f"❌ Error checking for multiple videos: {e}")
        return False


def get_video_url(driver, verbose=True):
    """Extracts the video URL from the video element."""
    return driver.execute_script("return document.querySelector('video')?.src;")


def extract_video_links(url, driver, chrome_driver_path, first_open, verbose=True):
    """Extracts all video links from the given Footballia match URL."""
    if verbose:
        print(f"📺 Extracting video links from: {url}")

    # driver = initialize_driver(chrome_driver_path)
    video_links = []
    video_count = 1

    try:
        driver.get(url)
        if first_open:
            time.sleep(4)
        else:
            time.sleep(1)

        close_popups(driver, verbose)
        time.sleep(0.25)
        close_popups(driver, verbose)
        login_to_footballia(driver, verbose)
        close_popups(driver, verbose)
        time.sleep(0.25)
        stop_page_loading(driver, verbose)
        time.sleep(0.25)
        click_video_to_start_stream(driver, verbose)
        close_popups(driver, verbose)
        time.sleep(0.25)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )

        if verbose:
            print("🔍 Extracting first video URL...")
        first_video_url = get_video_url(driver, verbose)
        if first_video_url:
            video_links.append(first_video_url)

        close_popups(driver, verbose)
        time.sleep(0.25)

        if check_and_click_next(driver, verbose):
            if verbose:
                print("🕒 Waiting for second video to load...")
            video_count += 1
            time.sleep(3)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )
            if verbose:
                print("🔍 Extracting second video URL...")
            second_video_url = get_video_url(driver, verbose)
            if second_video_url:
                video_links.append(second_video_url)

        if verbose:
            print(f"🎥 Video links found: {video_links}")
        return video_links, video_count

    except Exception as e:
        print(f"❌ Error extracting videos: {e}")
        return None

    finally:
        if verbose:
            print("🔄 Closing browser...")
        # driver.quit()
