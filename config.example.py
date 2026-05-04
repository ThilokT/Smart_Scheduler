"""
Configuration Template for Smart Scheduler

Copy this file to config.py and customize as needed.
"""

# ================= Gmail Configuration =================

# Default search query for finding relevant emails
# Uses Gmail's advanced search syntax
GMAIL_SEARCH_QUERY = "is:unread subject:(schedule OR meeting OR appointment)"

# Alternative query examples (uncomment to use):
# GMAIL_SEARCH_QUERY = "is:unread from:boss@company.com"
# GMAIL_SEARCH_QUERY = "is:unread subject:meeting newer_than:2d"
# GMAIL_SEARCH_QUERY = "is:unread label:important subject:schedule"

# Maximum messages to process per run
MAX_MESSAGES_PER_RUN = 10

# ================= Calendar Configuration =================

# Target timezone for all created events
# See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TARGET_TIMEZONE = "America/New_York"

# Alternative timezones:
# TARGET_TIMEZONE = "America/Los_Angeles"  # Pacific
# TARGET_TIMEZONE = "America/Chicago"      # Central
# TARGET_TIMEZONE = "Europe/London"        # UK
# TARGET_TIMEZONE = "Europe/Paris"         # Central European
# TARGET_TIMEZONE = "Asia/Tokyo"           # Japan
# TARGET_TIMEZONE = "Australia/Sydney"     # Australia

# Calendar ID (usually 'primary' for main calendar)
CALENDAR_ID = "primary"

# Send email invitations to attendees
SEND_EMAIL_UPDATES = False

# ================= Event Defaults =================

# Default event duration when not specified in email (hours)
DEFAULT_EVENT_DURATION = 1.0

# Default event color (1-11, see Google Calendar API docs)
# None = use default calendar color
DEFAULT_EVENT_COLOR = None

# Add reminders to created events
DEFAULT_REMINDERS = {
    'useDefault': False,
    'overrides': [
        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
        {'method': 'popup', 'minutes': 30},        # 30 minutes before
    ],
}

# Or use calendar's default reminders:
# DEFAULT_REMINDERS = {'useDefault': True}

# ================= Behavior Configuration =================

# Automatically mark processed emails as read
AUTO_MARK_AS_READ = True

# Add label to processed emails (None to disable)
PROCESSED_LABEL = None  # Example: "Smart-Scheduler/Processed"

# Skip emails older than this many days
MAX_EMAIL_AGE_DAYS = 7

# ================= NLP Configuration =================

# Time-related keywords to look for when parsing emails
TIME_KEYWORDS = [
    'schedule', 'meeting', 'appointment', 'call', 'sync',
    'discuss', 'review', 'catch up', 'meet', 'conference'
]

# Minimum confidence threshold for date parsing (0.0 - 1.0)
# Higher = more strict, fewer false positives
MIN_PARSE_CONFIDENCE = 0.5

# ================= Daemon Mode Configuration =================

# Interval between checks when running in daemon mode (minutes)
DAEMON_CHECK_INTERVAL = 10

# ================= File Paths =================

# OAuth credentials file (from Google Cloud Console)
CREDENTIALS_FILE = "credentials.json"

# Token storage file (auto-generated after first auth)
TOKEN_FILE = "token.json"

# ================= Logging Configuration =================

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = "INFO"

# Log file path (None for console only)
LOG_FILE = None  # Example: "smart_scheduler.log"

# ================= Advanced Configuration =================

# OAuth 2.0 Scopes required
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar"
]

# Alternative scope configurations:
# For modify access to Gmail (mark as read, add labels):
# SCOPES = [
#     "https://www.googleapis.com/auth/gmail.modify",
#     "https://www.googleapis.com/auth/calendar"
# ]

# For event-only calendar access (more restrictive):
# SCOPES = [
#     "https://www.googleapis.com/auth/gmail.readonly",
#     "https://www.googleapis.com/auth/calendar.events"
# ]

# API request timeout (seconds)
API_TIMEOUT = 30

# Retry configuration for failed API calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ================= Feature Flags =================

# Enable experimental features
ENABLE_LLM_PARSING = False  # Use LLM for better NLP (requires API key)
ENABLE_CONFLICT_DETECTION = False  # Check for calendar conflicts
ENABLE_LOCATION_EXTRACTION = False  # Parse meeting locations from emails
ENABLE_RICH_DESCRIPTIONS = False  # Add full email content to event description

# ================= External Service Configuration =================

# Slack webhook for notifications (None to disable)
SLACK_WEBHOOK_URL = None
# Example: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# OpenAI API key for LLM parsing (None to disable)
OPENAI_API_KEY = None
# Example: "sk-proj-..."

# ================= Customization Examples =================

# Example: Only process emails from specific domain
# GMAIL_SEARCH_QUERY = "is:unread from:@mycompany.com subject:meeting"

# Example: Different timezone for work events
# TARGET_TIMEZONE = "America/Chicago"

# Example: Longer default meetings
# DEFAULT_EVENT_DURATION = 1.5  # 90 minutes

# Example: Enable verbose logging
# LOG_LEVEL = "DEBUG"
# LOG_FILE = "debug.log"

# Example: Check every 5 minutes in daemon mode
# DAEMON_CHECK_INTERVAL = 5

# ================= Usage =================

# To use this configuration:
# 1. Copy this file to 'config.py'
# 2. Uncomment and modify settings as needed
# 3. Import in smart_scheduler.py:
#    from config import *
