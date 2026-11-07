"""Constants for the Toniebox integration."""


def is_tng_box(box: dict) -> bool:
    """Whether a Toniebox dict supports TNG-generation features (ICI/live control).

    The cloud's "generation" field only documents "classic", "rosered", "tng"
    (see API_DOC), but newer Toniebox 2 hardware reports other values there
    (e.g. "tb2g2") while still exposing the "tngSettings" feature flag. Check
    that flag instead of hardcoding "tng", so new generation strings keep
    working.
    """
    return "tngSettings" in (box.get("features") or [])


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
SORT_BY_RANDOM = "random"
SORT_OPTIONS = [SORT_BY_TITLE, SORT_BY_FILENAME, SORT_BY_DATE, SORT_BY_RANDOM]

# ── Shuffle-on-swap ────────────────────────────────────────────────────────────
# Local-only per-Creative-Tonie toggle: when the Tonie gets displaced on a box by
# a *different* Tonie, its chapters are shuffled (sort_by="random"). The switch
# state lives in a per-config-entry Store (no counterpart in the Tonie Cloud).
STORAGE_VERSION = 1
STORAGE_KEY_SHUFFLE = f"{DOMAIN}_shuffle"  # actual key gets the entry_id suffixed

# ── Volume boost per Tonie ─────────────────────────────────────────────────────
# Local-only per-Tonie multiplier: while that Tonie sits on a box, the box's max
# volume and current volume are raised by this factor; when it is removed (or
# replaced) the change is undone. Applied/active state is persisted so the undo
# survives a restart.
STORAGE_KEY_VOLUME_BOOST = f"{DOMAIN}_volume_boost"
VOLUME_MULTIPLIER_MIN = 1.0
VOLUME_MULTIPLIER_MAX = 3.0
MAX_VOLUME_STEPS = [25, 50, 75, 100]  # allowed values of the box's maxVolume
# Order matters: the box clamps the level to its *current* max, and a new max
# only reaches the box a few seconds after the cloud PATCH. So: raise max →
# wait for the box's settings confirmation → then raise the level and verify.
BOOST_SETTINGS_TIMEOUT = 20.0  # s to wait for the box to confirm new settings
BOOST_SETTLE_DELAY = 2.0       # s grace after confirmation / between retries
BOOST_LEVEL_WAIT = 5.0         # s to wait for the box to report its volume
BOOST_LEVEL_ATTEMPTS = 3       # level sends before giving up

# ICI (MQTT v5 real-time push)
ICI_HOST = "ici.tonie.cloud"
ICI_PORT = 443
ICI_TOPIC_BATTERY = "metrics/battery"
ICI_TOPIC_ONLINE = "online-state"
ICI_TOPIC_HEADPHONES = "metrics/headphones"
ICI_TOPIC_SETTINGS = "settings-applied"
# Verified against a live account: {"tonie": "<id>", "paused": bool, "chapter":
# int, "chapterUntilMs": <epoch ms>, "chapterDuration": <seconds>, "ended": bool,
# ...}. "tonie" is a flat ID string, not a nested object. An empty/None payload
# means the Tonie was removed from the box.
ICI_TOPIC_PLAYBACK = "playback/state"
# Live playback volume pushed by the box: {"level": N, "hardwarePercentage": P}
ICI_TOPIC_VOLUME = "volume/state"
# Box reply carrying the sleep-timer (stl) state:
#   {"stl": {"state": "on"|"off"|"completed", "duration": <s>, "until": <epoch>}}
ICI_TOPIC_BEDTIME = "app-reply/bedtime-state"

# ── ICI app-control commands (published by us / the official app) ──────────────
# Commands are published to: external/toniebox/{MAC}/app-control/{ICI_CMD_*}
ICI_CMD_PLAYBACK = "playback"      # {"action": "start"|"pause"|"setPosition", ...}
ICI_CMD_VOLUME = "volume"          # {"level": N}
ICI_CMD_SLEEP_TIMER = "stl"        # {"state": "on"|"off", "duration": <seconds>}
# Put the box to sleep NOW (it goes offline). The app sends stl(duration=300)
# then sleep({}).
ICI_CMD_SLEEP_NOW = "sleep"        # {}

# Toniebox volume "level" scale used by app-control/volume. Observed mapping
# (level -> hardware %): 1->5, 6->40, 7->50, 8->60. Extrapolated max for 100%.
ICI_VOLUME_MAX_LEVEL = 13
