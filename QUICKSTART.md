# Quick Start Guide

## 5-Minute Setup

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Get Google Credentials

1. **Visit:** https://console.cloud.google.com/
2. **Create Project** (or select existing)
3. **Enable APIs:**
   - Gmail API
   - Google Calendar API
4. **Create Credentials:**
   - APIs & Services → Credentials
   - Create OAuth Client ID
   - Type: Desktop App
   - Download as `credentials.json`
5. **Save File:**
   - Place `credentials.json` in the project folder

### Step 3: Run the Scheduler
```bash
python smart_scheduler.py
```

On first run:
- Browser opens automatically
- Sign in to Google
- Click "Allow" to grant permissions
- Done! The app saves your login

### Step 4: Test It Out

**Send yourself a test email:**

```
To: your_email@gmail.com
Subject: Schedule Test Meeting
Body: Let's meet tomorrow at 2 PM
```

Wait a moment, then run:
```bash
python smart_scheduler.py
```

Check your Google Calendar - you should see the event!

## Common Commands

**Process emails once:**
```bash
python smart_scheduler.py
```

**Run continuously (check every 10 minutes):**
```bash
python smart_scheduler.py --daemon
```

**Custom search (only emails from boss):**
```bash
python smart_scheduler.py --query "is:unread from:boss@company.com"
```

**Use different timezone:**
```bash
python smart_scheduler.py --timezone "Europe/London"
```

## Email Examples That Work

✅ "Meeting tomorrow at 3pm"
✅ "Call on Friday at 10:00 AM"
✅ "Schedule for Oct 15th at 2:30pm"
✅ "Let's sync next Tuesday at 4pm for 30 minutes"
✅ "Appointment on 2026-02-20 at 14:00"

## Troubleshooting

**"Missing credentials.json"**
→ Download from Google Cloud Console (Step 2 above)

**"Token refresh failed"**
→ Delete `token.json` and run again

**"No events created"**
→ Make sure email subject contains: schedule, meeting, or appointment
→ Or use custom query: `--query "is:unread"`

**Wrong timezone**
→ Use: `--timezone "Your/Timezone"`

## Next Steps

- Read [README.md](README.md) for full documentation
- Customize settings in `config.example.py`
- Set up as background service for automatic processing
- Add to cron for scheduled runs

## Need Help?

Check the full README.md or:
- Gmail API Docs: https://developers.google.com/gmail/api
- Calendar API Docs: https://developers.google.com/calendar

---

**🎉 You're all set! Your emails will now automatically become calendar events.**
