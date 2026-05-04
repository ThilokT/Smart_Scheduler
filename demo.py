#!/usr/bin/env python3
"""
Smart Scheduler Demo Mode

This script runs the Smart Scheduler in demo/dry-run mode for testing
without actually creating calendar events.
"""

import sys
import os

# Mock the necessary classes for demo
class DemoGmailClient:
    """Mock Gmail client that returns sample emails."""
    
    def search_messages(self, query="", max_results=10):
        """Return sample messages."""
        print(f"🔍 Searching Gmail with query: '{query}'")
        return [
            {"id": "demo_msg_001", "threadId": "thread_001"},
            {"id": "demo_msg_002", "threadId": "thread_002"},
            {"id": "demo_msg_003", "threadId": "thread_003"},
        ]
    
    def get_message_details(self, msg_id):
        """Return sample email data."""
        samples = {
            "demo_msg_001": {
                "id": "demo_msg_001",
                "subject": "Team Meeting Next Week",
                "body": "Hi everyone,\n\nLet's have our weekly team sync next Tuesday at 2 PM. Should take about an hour.\n\nThanks!",
                "sender": "Sarah Johnson <sarah@company.com>"
            },
            "demo_msg_002": {
                "id": "demo_msg_002",
                "subject": "Coffee Catch-up",
                "body": "Hey! Want to grab coffee tomorrow at 10am? Quick 30 minute chat.",
                "sender": "Mike Chen <mike@company.com>"
            },
            "demo_msg_003": {
                "id": "demo_msg_003",
                "subject": "Project Review",
                "body": "Let's review the project status on Friday, February 14th at 3:30 PM EST. We'll need 90 minutes.",
                "sender": "Jane Smith <jane@company.com>"
            }
        }
        return samples.get(msg_id)
    
    def mark_as_read(self, msg_id):
        """Mock marking as read."""
        print(f"  📧 Would mark message {msg_id[:12]}... as read")
        return True


class DemoCalendarClient:
    """Mock Calendar client that simulates event creation."""
    
    def create_event(self, event_data, source_msg_id, send_updates=False):
        """Simulate event creation."""
        print(f"  📅 Would create event:")
        print(f"     Title: {event_data['summary']}")
        print(f"     Start: {event_data['start'].strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"     End: {event_data['end'].strftime('%Y-%m-%d %H:%M %Z')}")
        
        duration = (event_data['end'] - event_data['start']).total_seconds() / 3600
        print(f"     Duration: {duration} hours")
        
        if 'attendees' in event_data:
            print(f"     Attendees: {', '.join([a['email'] for a in event_data['attendees']])}")
        
        print(f"     Description: {event_data['description'][:50]}...")
        return True


def run_demo():
    """Run the Smart Scheduler in demo mode."""
    print("=" * 70)
    print("SMART SCHEDULER - DEMO MODE")
    print("=" * 70)
    print()
    print("This demo simulates the Smart Scheduler workflow without:")
    print("  • Requiring Google credentials")
    print("  • Accessing your real Gmail account")
    print("  • Creating actual calendar events")
    print()
    print("It shows how the system would process sample emails.")
    print("=" * 70)
    print()
    
    # Import the EventExtractor (real one, since it doesn't need API)
    try:
        from smart_scheduler import EventExtractor
    except ImportError:
        print("⚠️  Could not import EventExtractor. Install dependencies:")
        print("   pip install python-dateutil")
        return
    
    # Create demo components
    gmail = DemoGmailClient()
    calendar = DemoCalendarClient()
    extractor = EventExtractor(default_tz_name="America/New_York")
    
    # Simulate the workflow
    query = "is:unread subject:(schedule OR meeting OR appointment)"
    messages = gmail.search_messages(query)
    
    print(f"Found {len(messages)} sample message(s)\n")
    
    success_count = 0
    
    for idx, msg in enumerate(messages, 1):
        print(f"[{idx}/{len(messages)}] Processing Message ID: {msg['id']}")
        
        # Get email details
        email_data = gmail.get_message_details(msg['id'])
        print(f"  Subject: \"{email_data['subject']}\"")
        
        # Parse intent
        event_data = extractor.extract_event_data(
            email_data['subject'],
            email_data['body'],
            email_data.get('sender')
        )
        
        if not event_data:
            print(f"  ✗ Could not extract valid date/time\n")
            continue
        
        # Create event (simulated)
        success = calendar.create_event(event_data, msg['id'])
        
        if success:
            success_count += 1
            gmail.mark_as_read(msg['id'])
        
        print()
    
    # Summary
    print("=" * 70)
    print(f"Demo Complete")
    print(f"  Successfully processed: {success_count}/{len(messages)}")
    print("=" * 70)
    print()
    print("To run with real data:")
    print("  1. Set up credentials (see QUICKSTART.md)")
    print("  2. Run: python smart_scheduler.py")
    print()


if __name__ == "__main__":
    run_demo()
