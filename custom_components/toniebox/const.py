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
