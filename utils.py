import json
from config import API_KEY
from google import genai

client = genai.Client(api_key=API_KEY)


def save_flop_data(flop_data, output_file="flop_data.json"):
    """Saves the processed flop data to a JSON file."""
    with open(output_file, "w") as f:
        json.dump(flop_data, f, indent=4)


async def delete_uploaded_files(uploaded_files):
    """Deletes all uploaded video files from the Gemini file system."""
    for file_obj in uploaded_files.values():
        if file_obj and hasattr(file_obj, "name"):
            try:
                client.files.delete(name=file_obj.name)
                print(f"Deleted file: {file_obj.name}")
            except Exception as e:
                print(f"Failed to delete file {file_obj.name}: {e}")


TEAM_NAME_MAP = {
    "BOU": "AFC Bournemouth",
    "ARS": "Arsenal",
    "AVL": "Aston Villa",
    "BRE": "Brentford",
    "BHA": "Brighton & Hove Albion",
    "CHE": "Chelsea",
    "CRY": "Crystal Palace",
    "EVE": "Everton",
    "FUL": "Fulham",
    "IPS": "Ipswich Town",
    "LEI": "Leicester City",
    "LIV": "Liverpool",
    "MCI": "Manchester City",
    "MUN": "Manchester United",
    "NEW": "Newcastle United",
    "NFO": "Nottingham Forest",
    "SOU": "Southampton",
    "TOT": "Tottenham Hotspur",
    "WHU": "West Ham United",
    "WOL": "Wolverhampton Wanderers",
}


def map_team_name(team_abbreviation):
    """Maps a team abbreviation to its full name. Returns the full name if found, otherwise returns the original."""
    return TEAM_NAME_MAP.get(team_abbreviation, team_abbreviation)
