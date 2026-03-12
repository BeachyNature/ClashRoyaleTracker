import os
import time
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

PLAYER_INFO = "json/player_info.json"
BASE_URL = "https://api.clashroyale.com/v1"
TEXT_URL = "https://api.textbee.dev/api/v1"

load_dotenv()
TEXTBEE_KEY = os.getenv("TEXTBEE_KEY")
DEVICE_ID = os.getenv("DEVICE_ID")
API_KEY = os.getenv("API_KEY")

global total_updates
total_updates = 0

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

class PlayerInfo:
    """ Class to represent player information and track win/lose streaks """

    def __init__(self, name: str="Unknown", number: str="Unknown", trophies: int=0):
        self.name = name
        self.number = number
        self.trophies = trophies
        self.win_streak = 0
        self.lose_streak = 0
        self.prev_trop = 0
        self.status = None
        self.last_login = None

    def update(self, value) -> None:
        """ Update the players trophy count """

        self.last_login = time.ctime()
        self.prev_trop = self.trophies

        if value > self.trophies:
            self.trophies = value
            self.status = "Winning"
            self.win_streak += 1
            self.lose_streak = 0
            return

        self.trophies = value
        self.status = "Losing"
        self.win_streak = 0
        self.lose_streak += 1
        return

def get_meme() -> None:
    """ Get link to meme to send along with message """

    response = requests.get("https://meme-api.com/gimme")
    if response.status_code == 200:
        meme_data = response.json()
        msg = f"\n{meme_data['title']}"
        msg += f"\n{meme_data['url']}"
        return msg
    return ""

def send_text(number_str: str, msg: str) -> None:
    """ Send a text message to the specified phone number using Gmail's SMTP server """
    
    if not number_str:
        print("No phone number provided. Skipping text message.")
        return

    try:
        msg += get_meme()
        msg += "\nYours truly,\nSickFish <3"
        url = f"{TEXT_URL}/gateway/devices/{DEVICE_ID}/send-sms"
        response = requests.post(
            url,
            json={"recipients": [number_str], "message": msg},
            headers={"x-api-key": TEXTBEE_KEY}
        )

        if response.status_code == 201:
            print(f"Message sent successfully to {number_str}!")
            return
        
        print(f"Failed to send message to {number_str}: {response.status_code} - {response.json()}")
        return
    except Exception as e:
        print(f"An error occurred while sending message to {number_str}: {e}")
        return

def send_reminder(player_dict: dict) -> None:
    """ Send text reminders to all players in the player data dictionary """

    msg =  "(Clash Royale Reminder)\n"
    msg += "Have you played Clash Royale today?\n"
    msg += "If not, you should get on it!"

    # Send broadcast reminder to all players in the player data dictionary
    for player in player_dict.values():
        # TODO: Check the last time the player was online
        send_text(player.number, msg)
        time.sleep(1)

def send_online(player_dict:dict, online: list) -> None:
    """ Send a text message when a player is online """

    msg = "(Clash Royale Alert)\nPlayer(s) Online:\n"
    for player in online:
        # Get the player update type
        status = "decreased"
        s_type = player.lose_streak
        if player.win_streak:
            status = "increased"
            s_type = player.win_streak

        msg += f"{player.name}: Trophies {status}"
        msg += f" from {player.prev_trop} to {player.trophies}\n"
        msg += f"{player.status} Streak: {s_type}\n"

    # Send broadcast reminder to all players in the player data dictionary
    for player in player_dict.values():
        send_text(player.number, msg)
        time.sleep(1)

def get_player_info(player_tag: str) -> dict:
    """ Fetch player information from the Clash Royale API """

    try:
        player_tag = player_tag.replace("#", "")
        url = f"{BASE_URL}/players/%23{player_tag}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()

        print(f"Error: {response.status_code} - {response.json()}")
        return response.json()
    except Exception as e:
        print(f"An error occurred while fetching player info: {e}")
        return None

def load_player_data() -> dict:
    """ Load player data from a JSON file, or return an empty dict if the file doesn't exist """

    if not os.path.exists(PLAYER_INFO):
        print("No existing player data found. Starting fresh.")
        return {}

    try:
        with open(PLAYER_INFO, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"An error occurred while reading {PLAYER_INFO}: {e}")
        return {}

def save_player_data(player_dict):
    """ Save player data to a JSON file """

    info = {}
    for tag, player in player_dict.items():
        info[tag] = {
            "name": player.name,
            "number": player.number,
            "trophies": player.trophies,
            "last_login": player.last_login
        }

    # Update json file
    with open(PLAYER_INFO, "w") as file:
        json.dump(info, file, indent=4)

def track_login(player_dict: dict) -> None:
    """ Track player login and trophy changes, saving data to a JSON file """
    
    online = []
    _dirty = False
    _inital = True
    global total_updates

    last_sent = time.time()
    next_run = time.time() + 28800
    next_day = datetime.now() + timedelta(days=1)

    # Get player data -------------------
    print("Player data loaded successfully. Starting tracking...")

    while True:
        current_time = time.time()
        if next_day < datetime.now():
            print(f"Total updates sent today: {total_updates}")
            next_day = datetime.now() + timedelta(days=1)
            total_updates = 0

        if total_updates > 100:
            print("Too many updates sent today. Waiting until tomorrow to send more.")
            time.sleep(3600)
            continue

        # Check each player for trophy changes and update data accordingly
        for player_tag in player_dict.keys():
            current_status = get_player_info(player_tag)
            player = player_dict[player_tag]

            # Check the current status
            if current_status:
                curr_trop = current_status["trophies"]
                prev_trop = player.trophies

                # Update trophies and last login time if there is a change in trophies
                if curr_trop != prev_trop:
                    if not _dirty:
                        print("Trophy change detected!")
                        _dirty = True

                    # Update player info
                    player.update(curr_trop)
                    online.append(player)

        if _dirty: # Send text message if a player is online
            print("Player(s) online. Preparing to send update...")
            save_player_data(player_dict)

            # Send message only if last message has not been sent within 3 minutes
            if _inital or ((current_time - last_sent) >= 180):
                send_online(player_dict, online)
                last_sent = current_time
                _dirty = False
                _inital = False
                online = []

        # Send text reminder every 8 hours (reminders)
        if current_time >= next_run:
            send_reminder(player_dict)
            next_run += 28800
        time.sleep(15)

# Setup all of the listed players -------
data = load_player_data()

player_dict = {}
for tag in data:
    player_dict[tag] = PlayerInfo(
        name=data[tag]["name"],
        number=data[tag]["number"],
        trophies=data[tag]["trophies"]
    )

# Start tracking users
print(f"{time.ctime()}: Starting Clash Royale Tracker...")
track_login(player_dict)
