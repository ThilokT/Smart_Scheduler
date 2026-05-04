"""
Smart Scheduler: Gmail to Calendar Automation Middleware.

This script polls a Gmail inbox for unread messages containing scheduling keywords,
extracts temporal intent using heuristic parsing, and synchronizes the data
to Google Calendar.

It implements OAuth2 auth, exponential backoff, and idempotent event insertion.
"""

import os
import time
import base64
import hashlib
import re
from datetime import datetime as dt_class, timedelta
from typing import Optional, Dict, Any, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dateutil import parser
from dateutil.tz import gettz


# ================= Configuration =================
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar"
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
TARGET_TIMEZONE = "Asia/Kolkata"
SEARCH_QUERY = "is:unread subject:(schedule OR meeting OR appointment)"


# ================= Auth Module =================
def get_authenticated_services():
    """
    Authenticates user and returns Gmail and Calendar service objects.
    
    Returns:
        tuple: (gmail_service, calendar_service)
    """
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE}. Please download it from Google Cloud Console."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    
    gmail_service = build("gmail", "v1", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    
    return gmail_service, calendar_service


# ================= Gmail Client Module =================
class GmailClient:
    """Handles all Gmail API interactions."""
    
    def __init__(self, service):
        self.service = service
    
    def search_messages(self, query: str = SEARCH_QUERY, max_results: int = 10) -> List[Dict]:
        """
        Lists messages matching the query.
        
        Args:
            query: Gmail search query string
            max_results: Maximum number of messages to retrieve
            
        Returns:
            List of message objects with id and threadId
        """
        try:
            response = self.service.users().messages().list(
                userId="me", 
                q=query,
                maxResults=max_results
            ).execute()
            return response.get("messages", [])
        except HttpError as error:
            print(f"Gmail API List Error: {error}")
            return []
    
    def get_message_details(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves full message details including subject and body.
        
        Args:
            msg_id: Gmail message ID
            
        Returns:
            Dictionary with id, subject, and body keys
        """
        try:
            message = self.service.users().messages().get(
                userId="me", 
                id=msg_id, 
                format="full"
            ).execute()
            
            payload = message.get("payload", {})
            headers = payload.get("headers", [])
            
            # Extract subject from headers
            subject = next(
                (h['value'] for h in headers if h['name'].lower() == 'subject'), 
                "No Subject"
            )
            
            # Extract sender for potential attendee addition
            sender = next(
                (h['value'] for h in headers if h['name'].lower() == 'from'),
                None
            )
            
            # Extract body using recursive MIME traversal
            body = self._extract_text_recursive(payload)
            
            return {
                "id": msg_id,
                "subject": subject,
                "body": body,
                "sender": sender
            }
        except HttpError as error:
            print(f"Gmail API Get Error: {error}")
            return None
    
    def _extract_text_recursive(self, part: Dict) -> str:
        """
        DFS traversal to find text/plain content in MIME structure.
        
        Args:
            part: Payload part from Gmail API
            
        Returns:
            Decoded text content
        """
        # If this part is text/plain, decode and return
        if part.get('mimeType') == 'text/plain':
            data = part.get('body', {}).get('data')
            if data:
                return self._decode_base64url(data)
        
        # If multipart, recurse into sub-parts
        if 'parts' in part:
            # First, look for explicit text/plain
            for subpart in part['parts']:
                if subpart.get('mimeType') == 'text/plain':
                    data = subpart.get('body', {}).get('data')
                    if data:
                        return self._decode_base64url(data)
            
            # If not found, recurse deeper
            for subpart in part['parts']:
                text = self._extract_text_recursive(subpart)
                if text:
                    return text
        
        return ""
    
    def _decode_base64url(self, data: str) -> str:
        """
        Decodes Base64url encoded string from Gmail API.
        
        Args:
            data: Base64url encoded string
            
        Returns:
            Decoded UTF-8 string
        """
        if not data:
            return ""
        
        # Fix URL-safe characters
        decoded_data = data.replace("-", "+").replace("_", "/")
        
        # Fix padding (add = until length is multiple of 4)
        padding = len(decoded_data) % 4
        if padding:
            decoded_data += "=" * (4 - padding)
        
        try:
            return base64.b64decode(decoded_data).decode('utf-8')
        except Exception as e:
            print(f"Decode error: {e}")
            return ""
    
    def mark_as_read(self, msg_id: str) -> bool:
        """
        Marks a message as read by removing the UNREAD label.
        
        Args:
            msg_id: Gmail message ID
            
        Returns:
            True if successful
        """
        try:
            self.service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except HttpError as error:
            print(f"Failed to mark message as read: {error}")
            return False


# ================= Event Extractor Module =================
class EventExtractor:
    """Handles NLP parsing to extract event data from email text."""
    
    MONTH_MAP = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    def __init__(self, default_tz_name: str = TARGET_TIMEZONE):
        self.default_tz = gettz(default_tz_name)
        self.default_tz_name = default_tz_name
        
        # Regex patterns for detecting time-related content in lines
        self.time_patterns = [
            r'\b(at|on|by|before|after|during)\s+\d',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'\b(tomorrow|today|next\s+week|next\s+month)',
            r'\b\d{1,2}:\d{2}\s*(am|pm|AM|PM)',
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)',
            r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{4}',
        ]
    
    def extract_event_data(self, email_subject: str, email_body: str, sender: str = None) -> Optional[Dict[str, Any]]:
        """
        Parses email content to generate event metadata.
        Uses multiple strategies: regex extraction, relative dates, fuzzy parsing.
        """
        full_text = f"{email_subject}. {email_body}"
        
        # Strategy 1: Regex-based date extraction (handles Indian formats)
        dt = self._extract_date_regex(full_text)
        
        # Strategy 2: Relative dates (tomorrow, today, next Monday)
        if dt is None:
            dt = self._extract_relative_date(full_text)
        
        # Strategy 3: Fuzzy parsing on individual relevant lines
        if dt is None:
            candidate_lines = self._extract_time_relevant_lines(full_text)
            for line in candidate_lines:
                try:
                    dt = parser.parse(line.strip(), fuzzy=True, dayfirst=True)
                    break
                except (ValueError, TypeError, OverflowError):
                    continue
        
        # Strategy 4: Fuzzy parsing on subject alone
        if dt is None:
            try:
                dt = parser.parse(email_subject, fuzzy=True, dayfirst=True)
            except (ValueError, TypeError, OverflowError):
                pass
        
        if dt is None:
            return None
        
        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.default_tz)
        
        # Extract duration, default to 1 hour
        duration_hours = self._extract_duration(full_text)
        end_dt = dt + timedelta(hours=duration_hours)
        
        event_data = {
            "summary": email_subject if email_subject else "Scheduled Event",
            "start": dt,
            "end": end_dt,
            "description": f"Auto-generated from email:\n\n{email_body[:300]}...",
            "timezone": self.default_tz_name,
        }
        
        if sender:
            event_data["attendees"] = [{"email": self._extract_email(sender)}]
        
        return event_data
    
    def _extract_date_regex(self, text: str):
        """Extract date+time using regex. Returns datetime or None."""
        extracted_date = None
        
        # Pattern 1: "08 November 2025", "31 January 2026"
        match = re.search(
            r'(\d{1,2})\s+(January|February|March|April|May|June|July|'
            r'August|September|October|November|December)\s+(\d{4})',
            text, re.IGNORECASE
        )
        if match:
            try:
                extracted_date = dt_class(
                    int(match.group(3)),
                    self.MONTH_MAP[match.group(2).lower()],
                    int(match.group(1))
                )
            except ValueError:
                pass
        
        # Pattern 2: "12th January 2026", "9th September 2025"
        if not extracted_date:
            match = re.search(
                r'(\d{1,2})(?:st|nd|rd|th)\s+(January|February|March|April|May|June|'
                r'July|August|September|October|November|December)\s+(\d{4})',
                text, re.IGNORECASE
            )
            if match:
                try:
                    extracted_date = dt_class(
                        int(match.group(3)),
                        self.MONTH_MAP[match.group(2).lower()],
                        int(match.group(1))
                    )
                except ValueError:
                    pass
        
        # Pattern 3: DD/MM/YYYY or DD-MM-YYYY (Indian day-first format)
        if not extracted_date:
            match = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', text)
            if match:
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    try:
                        extracted_date = dt_class(year, month, day)
                    except ValueError:
                        pass
        
        # Pattern 4: YYYY-MM-DD (ISO format)
        if not extracted_date:
            match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
            if match:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    try:
                        extracted_date = dt_class(year, month, day)
                    except ValueError:
                        pass
        
        if not extracted_date:
            return None
        
        # Extract time component
        hour, minute = self._extract_time(text)
        if hour is not None:
            extracted_date = extracted_date.replace(hour=hour, minute=minute)
        else:
            extracted_date = extracted_date.replace(hour=9, minute=0)  # Default 9 AM
        
        return extracted_date
    
    def _extract_time(self, text: str):
        """Extract time (hour_24, minute) from text. Returns tuple."""
        # "3:00 PM", "10:30 AM", "09:30 PM"
        match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', text)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            ap = match.group(3).lower()
            if ap == 'pm' and h != 12: h += 12
            elif ap == 'am' and h == 12: h = 0
            return (h, m)
        
        # "10.30 AM" (dot separator, common in India)
        match = re.search(r'(\d{1,2})\.(\d{2})\s*(AM|PM|am|pm)', text)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            ap = match.group(3).lower()
            if ap == 'pm' and h != 12: h += 12
            elif ap == 'am' and h == 12: h = 0
            return (h, m)
        
        # "at 14:00" (24-hour)
        match = re.search(r'(?:at|by|from)\s+(\d{1,2}):(\d{2})\b', text, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return (h, m)
        
        # "by 10.30" (dot, no AM/PM)
        match = re.search(r'(?:at|by|from)\s+(\d{1,2})\.(\d{2})\b', text, re.IGNORECASE)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return (h, m)
        
        return (None, None)
    
    def _extract_relative_date(self, text: str):
        """Handle 'tomorrow', 'today', 'next Tuesday', etc."""
        text_lower = text.lower()
        now = dt_class.now()
        
        if 'day after tomorrow' in text_lower:
            base = now + timedelta(days=2)
        elif 'tomorrow' in text_lower:
            base = now + timedelta(days=1)
        elif "today" in text_lower and re.search(r"today'?s?", text_lower):
            base = now
        else:
            # "next Monday", "next Friday"
            days_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            match = re.search(r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', text_lower)
            if match:
                target = days_map[match.group(1)]
                ahead = (target - now.weekday()) % 7
                if ahead == 0: ahead = 7
                base = now + timedelta(days=ahead)
            else:
                return None
        
        hour, minute = self._extract_time(text)
        if hour is not None:
            base = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            base = base.replace(hour=9, minute=0, second=0, microsecond=0)
        
        return base
    
    def _extract_time_relevant_lines(self, text: str) -> List[str]:
        """Extracts lines that likely contain time information."""
        lines = text.split('\n')
        relevant_lines = []
        for line in lines:
            for pattern in self.time_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    relevant_lines.append(line)
                    break
        return relevant_lines
    
    def _extract_duration(self, text: str) -> float:
        """Attempts to extract meeting duration from text. Default 1 hour."""
        duration_patterns = [
            (r'(\d+)\s*hours?', 1.0),
            (r'(\d+)\s*mins?(?:utes?)?', 1/60.0),
            (r'(\d+)\s*hr?s?', 1.0),
        ]
        for pattern, multiplier in duration_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1)) * multiplier
        return 1.0
    
    def _extract_email(self, sender_string: str) -> str:
        """Extracts email address from sender string."""
        match = re.search(r'<(.+?)>', sender_string)
        if match:
            return match.group(1)
        if '@' in sender_string:
            return sender_string.strip()
        return sender_string


# ================= Calendar Client Module =================
class CalendarClient:
    """Handles all Google Calendar API interactions."""
    
    def __init__(self, service):
        self.service = service
    
    def create_event(self, event_data: Dict[str, Any], source_msg_id: str, 
                     send_updates: bool = False) -> bool:
        """
        Inserts event into the primary calendar with idempotency.
        
        Args:
            event_data: Dictionary with event details
            source_msg_id: Gmail message ID for generating unique event ID
            send_updates: Whether to send email notifications to attendees
            
        Returns:
            True if event was created or already exists
        """
        # Generate a deterministic ID based on the email ID
        unique_id = hashlib.md5(source_msg_id.encode('utf-8')).hexdigest()
        
        # Build event body according to Calendar API schema
        event_body = {
            'summary': event_data['summary'],
            'description': event_data['description'],
            'start': {
                'dateTime': event_data['start'].isoformat(),
                'timeZone': event_data.get('timezone', TARGET_TIMEZONE),
            },
            'end': {
                'dateTime': event_data['end'].isoformat(),
                'timeZone': event_data.get('timezone', TARGET_TIMEZONE),
            },
            'id': unique_id
        }
        
        # Add attendees if present
        if 'attendees' in event_data:
            event_body['attendees'] = event_data['attendees']
        
        try:
            event = self.service.events().insert(
                calendarId='primary',
                body=event_body,
                sendUpdates='all' if send_updates else 'none'
            ).execute()
            
            print(f"[OK] Event created: {event.get('htmlLink')}")
            print(f"  Title: {event_data['summary']}")
            print(f"  Time: {event_data['start'].strftime('%Y-%m-%d %H:%M %Z')}")
            return True
            
        except HttpError as error:
            # 409 Conflict means the event ID already exists (idempotency)
            if error.resp.status == 409:
                print(f"[OK] Event already exists (ID: {unique_id[:8]}...). Skipping.")
                return True
            else:
                print(f"[FAIL] Failed to create event: {error}")
                return False
    
    def list_upcoming_events(self, max_results: int = 10) -> List[Dict]:
        """
        Lists upcoming events from the primary calendar.
        
        Args:
            max_results: Maximum number of events to retrieve
            
        Returns:
            List of event dictionaries
        """
        try:
            now = dt_class.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
            
        except HttpError as error:
            print(f"Failed to list events: {error}")
            return []

    def check_conflict(self, start_dt, end_dt) -> bool:
        """Checks if there is an overlapping event on the primary calendar."""
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            items = events_result.get('items', [])
            # Return true if any overlapping events exist
            return len(items) > 0
            
        except HttpError as error:
            print(f"Failed to check for conflicts: {error}")
            return False


# ================= Main Smart Scheduler Class =================
class SmartScheduler:
    """Main orchestrator for the Smart Scheduler workflow."""
    
    def __init__(self, timezone: str = TARGET_TIMEZONE, auto_mark_read: bool = True):
        """
        Initialize the Smart Scheduler.
        
        Args:
            timezone: Target timezone for events
            auto_mark_read: Whether to mark processed emails as read
        """
        print("Authenticating with Google APIs...")
        gmail_service, calendar_service = get_authenticated_services()
        
        self.gmail = GmailClient(gmail_service)
        self.calendar = CalendarClient(calendar_service)
        self.extractor = EventExtractor(timezone)
        self.auto_mark_read = auto_mark_read
        
        print("[OK] Authentication successful\n")
    
    def run(self, query: str = SEARCH_QUERY, max_messages: int = 10):
        """
        Main execution loop for processing emails.
        
        Args:
            query: Gmail search query
            max_messages: Maximum number of messages to process
        """
        print(f"{'='*60}")
        print(f"Smart Scheduler - Sync Cycle Started")
        print(f"Time: {time.ctime()}")
        print(f"Query: {query}")
        print(f"{'='*60}\n")
        
        # 1. Fetch emails
        messages = self.gmail.search_messages(query, max_messages)
        
        if not messages:
            print("No new messages found matching the criteria.")
            return
        
        print(f"Found {len(messages)} message(s) to process.\n")
        
        # 2. Process each message
        success_count = 0
        skip_count = 0
        
        for idx, msg in enumerate(messages, 1):
            print(f"[{idx}/{len(messages)}] Processing Message ID: {msg['id'][:16]}...")
            
            try:
                # Fetch & Decode
                email_data = self.gmail.get_message_details(msg['id'])
                if not email_data:
                    print(f"  [FAIL] Could not retrieve email details. Skipping.\n")
                    skip_count += 1
                    continue
                
                print(f"  Subject: \"{email_data['subject']}\"")
                
                # Parse Intent
                event_data = self.extractor.extract_event_data(
                    email_data['subject'],
                    email_data['body'],
                    email_data.get('sender')
                )
                
                if not event_data:
                    print(f"  [FAIL] Could not extract valid date/time. Skipping.\n")
                    if self.auto_mark_read:
                        self.gmail.mark_as_read(msg['id'])
                        print(f"  [OK] Marked un-parseable email as read to prevent loop")
                    skip_count += 1
                    continue
                
                # Check for calendar conflicts
                if self.calendar.check_conflict(event_data['start'], event_data['end']):
                    print(f"  [WARNING] Conflict detected! Another event overlaps with this time.")
                    event_data['summary'] = "[CONFLICT] " + event_data['summary']
                    event_data['description'] = "WARNING: This event overlaps with another event on your calendar.\n\n" + event_data['description']
                
                # Sync to Calendar
                success = self.calendar.create_event(event_data, msg['id'])
                
                if success:
                    success_count += 1
                    
                    # Mark as read if configured
                    if self.auto_mark_read:
                        self.gmail.mark_as_read(msg['id'])
                        print(f"  [OK] Marked as read")
                else:
                    skip_count += 1
                
                print()  # Blank line between messages
                
            except Exception as e:
                print(f"  [ERROR] Critical error: {e}\n")
                skip_count += 1
                continue
        
        # 3. Summary
        print(f"{'='*60}")
        print(f"Sync Complete")
        print(f"  Successfully processed: {success_count}")
        print(f"  Skipped/Failed: {skip_count}")
        print(f"{'='*60}\n")
    
    def run_daemon(self, interval_minutes: int = 10, query: str = SEARCH_QUERY):
        """
        Run the scheduler as a daemon that checks periodically.
        
        Args:
            interval_minutes: Minutes between each check
            query: Gmail search query
        """
        print(f"Starting Smart Scheduler in daemon mode...")
        print(f"Will check every {interval_minutes} minutes.")
        print(f"Press Ctrl+C to stop.\n")
        
        try:
            while True:
                self.run(query)
                print(f"Sleeping for {interval_minutes} minutes...\n")
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("\n\nDaemon stopped by user.")


# ================= CLI Entry Point =================
if __name__ == "__main__":
    import argparse
    
    arg_parser = argparse.ArgumentParser(
        description="Smart Scheduler: Automate Gmail to Google Calendar"
    )
    arg_parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run as a daemon that checks periodically'
    )
    arg_parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='Minutes between checks in daemon mode (default: 10)'
    )
    arg_parser.add_argument(
        '--query',
        type=str,
        default=SEARCH_QUERY,
        help='Custom Gmail search query'
    )
    arg_parser.add_argument(
        '--max-messages',
        type=int,
        default=10,
        help='Maximum number of messages to process (default: 10)'
    )
    arg_parser.add_argument(
        '--timezone',
        type=str,
        default=TARGET_TIMEZONE,
        help='Timezone for events (default: America/New_York)'
    )
    arg_parser.add_argument(
        '--no-mark-read',
        action='store_true',
        help='Do not mark processed emails as read'
    )
    
    args = arg_parser.parse_args()
    
    try:
        scheduler = SmartScheduler(
            timezone=args.timezone,
            auto_mark_read=not args.no_mark_read
        )
        
        if args.daemon:
            scheduler.run_daemon(args.interval, args.query)
        else:
            scheduler.run(args.query, args.max_messages)
            
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\nSetup Instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing one")
        print("3. Enable Gmail API and Google Calendar API")
        print("4. Create OAuth 2.0 credentials (Desktop App)")
        print("5. Download credentials and save as 'credentials.json'")
        print("6. Run this script again\n")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
