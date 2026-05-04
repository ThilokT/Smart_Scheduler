# Smart Scheduler Architecture Documentation

## System Overview

The Smart Scheduler is a Python-based middleware application that automates the conversion of email-based scheduling requests into structured Google Calendar events. It operates as a unidirectional data pipeline with four distinct processing stages.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SMART SCHEDULER SYSTEM                        │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                ┌──────────────────┴──────────────────┐
                │                                      │
       ┌────────▼────────┐                   ┌────────▼────────┐
       │  Gmail Service  │                   │ Calendar Service │
       │   (Read-Only)   │                   │  (Read/Write)   │
       └────────┬────────┘                   └────────▲────────┘
                │                                      │
                │ OAuth 2.0                   OAuth 2.0│
                │ gmail.readonly              calendar │
                │                                      │
┌───────────────▼──────────────────────────────────────┴──────────────┐
│                     PROCESSING PIPELINE                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐│
│  │ 1. INGESTION │→ │2.NORMALIZATION│→│3.EXTRACTION │→│4.SYNC   ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────┘│
│                                                                      │
│  Gmail API         MIME Decoder      NLP Engine       Calendar API  │
│  - Query Filter    - Base64url       - dateutil       - Event      │
│  - Message List    - Recursive       - Fuzzy Parse    - Idempotency │
│  - Full Fetch      - Text Extract    - TZ Aware       - MD5 Hash   │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │                      │
                 ┌──────▼─────┐        ┌──────▼─────┐
                 │   token    │        │credentials │
                 │   .json    │        │   .json    │
                 └────────────┘        └────────────┘
```

## Component Architecture

### 1. Authentication Module (`get_authenticated_services`)

**Responsibility:** OAuth 2.0 credential management

**Flow:**
```
START
  │
  ├─► Check token.json exists?
  │     ├─► YES: Load credentials
  │     │      └─► Valid & not expired?
  │     │           ├─► YES: Return services
  │     │           └─► NO: Check refresh token?
  │     │                 ├─► YES: Refresh & save
  │     │                 └─► NO: Re-authorize
  │     └─► NO: Check credentials.json?
  │           ├─► YES: Start OAuth flow
  │           │      └─► Save token.json
  │           └─► NO: Error (file not found)
  │
  └─► Build services
       ├─► Gmail API v1
       └─► Calendar API v3
```

**Security Features:**
- Least privilege scopes
- Automatic token refresh
- Persistent credential storage
- Error recovery on revocation

### 2. Gmail Client (`GmailClient`)

**Key Methods:**

```python
search_messages(query, max_results)
├─► users().messages().list()
└─► Returns: List[{id, threadId}]

get_message_details(msg_id)
├─► users().messages().get(format='full')
├─► _extract_text_recursive(payload)
│   └─► Depth-first search for text/plain
├─► _decode_base64url(data)
│   ├─► Replace URL-safe chars (- → +, _ → /)
│   ├─► Add padding (=)
│   └─► Base64 decode → UTF-8
└─► Returns: {id, subject, body, sender}

mark_as_read(msg_id)
└─► users().messages().modify()
    └─► removeLabelIds: ["UNREAD"]
```

**MIME Traversal Algorithm:**
```
function extract_text(part):
    if part.mimeType == "text/plain":
        return decode(part.body.data)
    
    if part has sub-parts:
        for each subpart:
            # Prefer text/plain
            if subpart.mimeType == "text/plain":
                return decode(subpart.body.data)
        
        # Recursive fallback
        for each subpart:
            text = extract_text(subpart)
            if text exists:
                return text
    
    return empty
```

### 3. Event Extractor (`EventExtractor`)

**NLP Processing Pipeline:**

```
Email Text
    │
    ├─► Pre-filter
    │   ├─► Extract lines with time patterns
    │   │   └─► Regex: (at|on|by|tomorrow|friday|pm|am...)
    │   └─► Fallback: First 1000 characters
    │
    ├─► Fuzzy Parse
    │   ├─► dateutil.parser.parse(fuzzy=True)
    │   └─► Skips non-date tokens
    │
    ├─► Timezone Injection
    │   ├─► Check tzinfo == None?
    │   └─► Apply: datetime.replace(tzinfo=default_tz)
    │
    ├─► Duration Extraction
    │   ├─► Regex patterns:
    │   │   ├─► "(\d+) hours?" → multiply by 1.0
    │   │   ├─► "(\d+) mins?" → multiply by 1/60
    │   │   └─► Default: 1.0 hour
    │   └─► end = start + timedelta(hours=duration)
    │
    └─► Event Construction
        ├─► summary: email subject
        ├─► start: parsed datetime
        ├─► end: start + duration
        ├─► description: email body (first 300 chars)
        └─► attendees: extracted from sender
```

**Time Pattern Regex:**
```regex
\b(at|on|by|before|after|during)\s+\d
\b(monday|tuesday|...|sunday)
\b(tomorrow|today|next\s+week)
\b\d{1,2}:\d{2}\s*(am|pm|AM|PM)
\b(january|february|...|december)
```

### 4. Calendar Client (`CalendarClient`)

**Event Creation Flow:**

```
Input: event_data, source_msg_id
    │
    ├─► Generate Idempotency Key
    │   └─► MD5(source_msg_id) → hexdigest
    │
    ├─► Build Event Body (JSON)
    │   ├─► summary
    │   ├─► description
    │   ├─► start: {dateTime, timeZone}
    │   ├─► end: {dateTime, timeZone}
    │   ├─► attendees: [{email}]
    │   └─► id: idempotency key
    │
    ├─► API Call
    │   └─► events().insert(calendarId='primary', body=event_body)
    │
    └─► Error Handling
        ├─► 409 Conflict → Event exists (SUCCESS)
        ├─► 4xx/5xx → Log error (FAIL)
        └─► 200 OK → Event created (SUCCESS)
```

**Idempotency Mechanism:**
```
Email ID: "16a3f2b4c5d6e7f8"
         │
         ├─► MD5 Hash
         │   └─► "a1b2c3d4e5f6..."
         │
         └─► Same email processed twice?
             ├─► First run: Creates event (200 OK)
             └─► Second run: 409 Conflict (treated as success)
```

## Data Flow

### Complete Processing Sequence

```
1. USER SENDS EMAIL
   To: user@gmail.com
   Subject: "Team Meeting"
   Body: "Let's meet tomorrow at 2 PM"
   
2. SMART SCHEDULER RUNS
   ├─► Authenticate (OAuth 2.0)
   │   └─► Load token.json or re-authorize
   │
   ├─► Search Gmail
   │   ├─► Query: "is:unread subject:(schedule OR meeting)"
   │   └─► Result: [{id: "16a3f2b4c5d6e7f8", ...}]
   │
   ├─► Fetch Message
   │   ├─► GET /gmail/v1/users/me/messages/16a3f2b4c5d6e7f8
   │   └─► Extract:
   │       ├─► Subject: "Team Meeting"
   │       ├─► Body: "Let's meet tomorrow at 2 PM"
   │       └─► Sender: "boss@company.com"
   │
   ├─► Parse Intent
   │   ├─► Input: "Let's meet tomorrow at 2 PM"
   │   ├─► dateutil.parser.parse(fuzzy=True)
   │   └─► Output:
   │       ├─► start: 2026-02-06 14:00:00-05:00 (EST)
   │       └─► end:   2026-02-06 15:00:00-05:00 (EST)
   │
   ├─► Create Calendar Event
   │   ├─► Event ID: MD5("16a3f2b4c5d6e7f8")
   │   ├─► POST /calendar/v3/calendars/primary/events
   │   └─► Body:
   │       {
   │         "id": "a1b2c3d4e5f6...",
   │         "summary": "Team Meeting",
   │         "start": {"dateTime": "2026-02-06T14:00:00-05:00"},
   │         "end": {"dateTime": "2026-02-06T15:00:00-05:00"},
   │         "attendees": [{"email": "boss@company.com"}]
   │       }
   │
   └─► Mark Email as Read
       └─► PATCH /gmail/v1/users/me/messages/16a3f2b4c5d6e7f8/modify
```

## Error Handling & Resilience

### Error Categories

**1. Authentication Errors**
```python
try:
    creds.refresh(Request())
except Exception:
    # Token revoked or corrupted
    # → Delete token.json
    # → Re-trigger OAuth flow
```

**2. API Errors**
```python
except HttpError as error:
    if error.resp.status == 409:
        # Conflict: Event already exists
        # → SUCCESS (idempotency working)
    elif error.resp.status == 403:
        # Rate limit or permission denied
        # → Exponential backoff
    elif error.resp.status >= 500:
        # Server error
        # → Retry with backoff
    else:
        # Other errors
        # → Log and skip
```

**3. Parsing Errors**
```python
try:
    dt = parser.parse(text, fuzzy=True)
except (ValueError, OverflowError):
    # No valid date found
    # → Return None
    # → Skip this email
```

### Retry Strategy (Exponential Backoff)

```python
max_retries = 3
base_delay = 2  # seconds

for attempt in range(max_retries):
    try:
        # Make API call
        break
    except HttpError as e:
        if e.resp.status in [403, 503]:  # Rate limit or unavailable
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
        else:
            raise
```

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| OAuth Refresh | O(1) | Single HTTP request |
| Gmail Search | O(1) | Indexed search on Google's servers |
| Email Fetch | O(n) | n = number of messages |
| MIME Traverse | O(d) | d = depth of MIME tree (usually < 5) |
| NLP Parse | O(m) | m = length of text (limited to 1000 chars) |
| Event Create | O(1) | Single HTTP request per event |
| **Total** | **O(n)** | Linear in number of emails |

### Space Complexity

| Component | Memory Usage | Notes |
|-----------|--------------|-------|
| Credentials | ~2 KB | OAuth tokens (JSON) |
| Email Cache | ~10 KB per email | Full message with headers |
| Parsed Events | ~1 KB per event | Structured datetime objects |
| **Peak** | **~100 MB** | With dependencies loaded |

### API Quota Usage

**Gmail API:**
- List: 5 quota units per call
- Get: 5 quota units per message
- Modify: 10 quota units per message

**Calendar API:**
- Insert: 2 quota units per event

**Example:** Processing 10 emails
- Search: 5 units
- Fetch (10 emails): 50 units
- Create events (10): 20 units
- Mark as read (10): 100 units
- **Total: 175 units** (well below daily limit of 1,000,000,000)

## Security Considerations

### OAuth 2.0 Implementation

**Token Storage:**
```json
// token.json (NEVER COMMIT TO GIT)
{
  "token": "ya29.a0AfH6...",           // Access token (1 hour TTL)
  "refresh_token": "1//0gH9...",       // Refresh token (persistent)
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "123456789.apps.googleusercontent.com",
  "client_secret": "GOCSPX-...",      // From credentials.json
  "scopes": ["gmail.readonly", "calendar"]
}
```

**Security Best Practices:**
1. ✅ Minimal scopes (read-only Gmail)
2. ✅ Credentials in `.gitignore`
3. ✅ Token refresh automatic
4. ✅ HTTPS-only communication
5. ✅ No password storage
6. ✅ User can revoke anytime

### Data Privacy

**What the app accesses:**
- Email subjects and bodies (processed, not stored)
- Email sender addresses
- Calendar write access

**What the app does NOT access:**
- Passwords
- Full inbox (only matching emails)
- Contacts
- Drive files
- Other Google services

**Data retention:**
- Email content: In-memory only (discarded after processing)
- Tokens: Stored locally in `token.json`
- No cloud storage
- No third-party servers

## Deployment Scenarios

### 1. Local Development
```bash
python smart_scheduler.py
```

### 2. Cron Job (Periodic)
```cron
*/10 * * * * cd /path/to/smart_scheduler && python3 smart_scheduler.py
```

### 3. Systemd Service (Daemon)
```ini
[Service]
ExecStart=/usr/bin/python3 /path/to/smart_scheduler.py --daemon
Restart=always
```

### 4. Docker Container
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY smart_scheduler.py .
CMD ["python", "smart_scheduler.py", "--daemon"]
```

### 5. Cloud Function (Event-Driven)
```python
# Use Gmail API watch() with Pub/Sub
# Trigger: New email → Pub/Sub → Cloud Function
# No polling needed
```

## Extension Points

### Custom NLP Providers

```python
class LLMExtractor(EventExtractor):
    def extract_event_data(self, subject, body, sender):
        # Call OpenAI/Gemini API
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"Extract meeting details: {body}"
            }]
        )
        # Parse structured response
        return json.loads(response['choices'][0]['message']['content'])
```

### Multi-Calendar Support

```python
def route_to_calendar(event_data):
    if 'work' in event_data['summary'].lower():
        return 'work@example.com'
    else:
        return 'primary'
```

### Conflict Detection

```python
def check_conflicts(start, end):
    existing = calendar.events().list(
        timeMin=start.isoformat(),
        timeMax=end.isoformat()
    ).execute()
    return len(existing.get('items', [])) > 0
```

## Testing Strategy

### Unit Tests
- ✅ Base64url decoding
- ✅ MIME traversal
- ✅ Timezone conversion
- ✅ Duration extraction
- ✅ Idempotency key generation

### Integration Tests
- ✅ OAuth flow simulation
- ✅ End-to-end email processing
- ✅ Calendar event verification

### Test Coverage
```bash
python test_smart_scheduler.py
```

## Monitoring & Logging

### Key Metrics
- Emails processed per run
- Success rate (events created / emails processed)
- Average processing time per email
- API quota usage
- Error frequency by type

### Logging Levels
```python
DEBUG:   API request/response details
INFO:    Processing progress, events created
WARNING: Parsing failures, skipped emails
ERROR:   API errors, authentication failures
```

---

**Document Version:** 1.0  
**Last Updated:** February 2026  
**Author:** Smart Scheduler Development Team
