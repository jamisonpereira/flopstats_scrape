from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

FOOTBALLIA_EMAIL = os.getenv("FOOTBALLIA_EMAIL")
FOOTBALLIA_PASSWORD = os.getenv("FOOTBALLIA_PASSWORD")
FOOTBALLIA_USERNAME = os.getenv("FOOTBALLIA_USERNAME")


from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Replace with actual credentials
EMAIL = "jamison.pereira@gmail.com"
PASSWORD = "rch7rnt5qfj2wgx.WAH"
USERNAME = "jamison.pereira"


def initialize_driver(chrome_driver_path):
    """Initializes and returns a Selenium WebDriver instance with necessary options."""
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # Run without opening browser
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(chrome_driver_path)
    return webdriver.Chrome(service=service, options=chrome_options)


def close_popups(driver):
    """Clicks in the upper-left corner of the viewport to close pop-ups."""
    try:
        print("🛑 Closing pop-ups by clicking in the upper-left corner...")
        action = ActionChains(driver)
        action.move_by_offset(10, 10).click().perform()
        time.sleep(0.25)
        action.move_by_offset(10, 10).click().perform()
        print("✅ Pop-ups dismissed.")
    except Exception as e:
        print(f"⚠️ Could not dismiss pop-ups: {e}")


def login_to_footballia(driver):
    """Logs into Footballia using the dropdown login form."""
    print("🔑 Attempting login...")

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    try:
        print("📂 Clicking the 'Sign in' dropdown toggle...")
        dropdowns = driver.find_elements(
            By.CSS_SELECTOR, "a.dropdown-toggle[data-toggle='dropdown']"
        )
        if len(dropdowns) > 1:
            dropdowns[1].click()
            print("✅ Sign in dropdown opened.")
            time.sleep(0.5)
        else:
            print("⚠️ Could not find the correct dropdown.")
            return
    except Exception as e:
        print(f"⚠️ Unable to click dropdown: {e}")
        return

    try:
        print("🕒 Waiting for login form...")
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "new_user"))
        )
        print("✅ Login form found.")

        driver.find_element(By.ID, "user_email").send_keys(EMAIL)
        driver.find_element(By.ID, "user_password").send_keys(PASSWORD)

        print("🔓 Submitting login form...")
        driver.find_element(By.NAME, "commit").click()

        print("🕒 Waiting for confirmation...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    f"//li[contains(@class, 'dropdown')]//span[contains(text(), '{USERNAME}')]",
                )
            )
        )
        print("✅ Login successful.")
    except Exception as e:
        print(f"⚠️ Login failed: {e}")


def click_video_to_start_stream(driver):
    """Clicks the play button to start the video."""
    print("🎬 Starting video stream...")

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "video"))
        )
        print("✅ Video container found.")

        play_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "jwplayer_display_button"))
        )
        play_button.click()
        time.sleep(3)
        print("✅ Video playing.")
    except Exception as e:
        print(f"⚠️ Video did not start: {e}")


def check_and_click_next(driver):
    """Checks if the match has two videos and clicks the 'Next' button if needed."""
    print("🔍 Checking for multiple video files...")

    try:
        warnings = driver.find_elements(By.CLASS_NAME, "alert-warning")
        for warning in warnings:
            if "This match is divided in 2 files" in warning.text:
                print("🟡 Match has two videos.")

                try:
                    print("⏭ Locating 'Next' button...")
                    next_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".jwnext button")
                        )
                    )
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", next_button
                    )
                    time.sleep(1)

                    try:
                        print("⏭ Clicking 'Next' button...")
                        next_button.click()
                        time.sleep(3)
                        print("✅ Advanced to second video.")
                        return True
                    except:
                        print("⚠️ Normal click failed, trying JavaScript click...")
                        driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(3)
                        print("✅ JavaScript click successful.")
                        return True

                except Exception as e:
                    print(f"⚠️ Could not locate 'Next' button: {e}")
                    return False

        print("✅ Single video detected.")
        return False
    except Exception as e:
        print(f"❌ Error checking for multiple videos: {e}")
        return False


def get_video_url(driver):
    """Extracts the video URL from the video element."""
    return driver.execute_script("return document.querySelector('video')?.src;")


def extract_video_links(url, chrome_driver_path):
    """Extracts all video links from the given Footballia match URL."""
    print("TESTING NEW ONE!!!")
    print(f"📺 Extracting video links from: {url}")

    driver = initialize_driver(chrome_driver_path)
    video_links = []

    try:
        driver.get(url)
        time.sleep(5)

        close_popups(driver)
        login_to_footballia(driver)
        click_video_to_start_stream(driver)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )

        print("🔍 Extracting first video URL...")
        first_video_url = get_video_url(driver)
        if first_video_url:
            video_links.append(first_video_url)

        if check_and_click_next(driver):
            print("🕒 Waiting for second video to load...")
            time.sleep(4)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )
            print("🔍 Extracting second video URL...")
            second_video_url = get_video_url(driver)
            if second_video_url:
                video_links.append(second_video_url)

        print(f"🎥 Video links found: {video_links}")
        return video_links

    except Exception as e:
        print(f"❌ Error extracting videos: {e}")
        return None

    finally:
        print("🔄 Closing browser...")
        driver.quit()
        print("✅ Selenium session ended.")
