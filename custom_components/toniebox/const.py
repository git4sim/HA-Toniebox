"""Constants for the Toniebox integration."""

DOMAIN = "toniebox"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Coordinator
UPDATE_INTERVAL_MINUTES = 5

# A Toniebox is considered offline after this many minutes of no last_seen update
TONIEBOX_ONLINE_TIMEOUT_MINUTES = 30

# Platform names
PLATFORM_MEDIA_PLAYER = "media_player"
PLATFORM_SENSOR = "sensor"
PLATFORM_BUTTON = "button"
PLATFORM_SELECT = "select"

# Attributes
ATTR_HOUSEHOLD_ID = "household_id"
ATTR_TONIE_ID = "tonie_id"
ATTR_CHAPTERS = "chapters"
ATTR_CHAPTER_COUNT = "chapter_count"
ATTR_IMAGE_URL = "image_url"

# Services
SERVICE_UPLOAD_AUDIO = "upload_audio"
SERVICE_REMOVE_CHAPTER = "remove_chapter"
SERVICE_CLEAR_CHAPTERS = "clear_chapters"
SERVICE_SORT_CHAPTERS = "sort_chapters"
SERVICE_MOVE_CHAPTER = "move_chapter"

# Sort modes
SORT_BY_TITLE = "title"
SORT_BY_FILENAME = "filename"
SORT_BY_DATE = "date"
SORT_OPTIONS = [SORT_BY_TITLE, SORT_BY_FILENAME, SORT_BY_DATE]

# ICI (MQTT v5 real-time push)
ICI_HOST = "ici.tonie.cloud"
ICI_PORT = 443
ICI_TOPIC_BATTERY = "metrics/battery"
ICI_TOPIC_ONLINE = "online-state"
ICI_TOPIC_HEADPHONES = "metrics/headphones"
ICI_TOPIC_SETTINGS = "settings-applied"
ICI_TOPIC_PLAYBACK = "playback/state"
# Live playback volume pushed by the box: {"level": N, "hardwarePercentage": P}
ICI_TOPIC_VOLUME = "volume/state"
# Box reply carrying the sleep-timer (stl) state:
#   {"stl": {"state": "on"|"off"|"completed", "duration": <s>, "until": <epoch>}}
ICI_TOPIC_BEDTIME = "app-reply/bedtime-state"

# Sleep-timer dropdown options -> duration in seconds ("off" cancels the timer).
SLEEP_TIMER_OPTIONS: dict[str, int | None] = {
    "off": None,
    "15": 900,
    "30": 1800,
    "60": 3600,
}

# ── ICI app-control commands (published by us / the official app) ──────────────
# Verified by capturing the official Tonies app's MQTT traffic (see
# tests/capture_commands.py). Commands are published to:
#   external/toniebox/{MAC}/app-control/{ICI_CMD_*}
ICI_CMD_PLAYBACK = "playback"      # {"action": "start"|"pause"|"setPosition", ...}
ICI_CMD_VOLUME = "volume"          # {"level": N}
ICI_CMD_SLEEP_TIMER = "stl"        # {"state": "on"|"off", "duration": <seconds>}
# Put the box to sleep NOW (it goes offline). The app sends stl(duration=300)
# then sleep({}); verified live — box reported online-state "offline" after.
ICI_CMD_SLEEP_NOW = "sleep"        # {}

# Toniebox volume "level" scale used by app-control/volume. Observed mapping
# (level -> hardware %): 1->5, 6->40, 7->50, 8->60. Extrapolated max for 100%.
ICI_VOLUME_MAX_LEVEL = 13