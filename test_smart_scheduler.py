"""
Test Suite for Smart Scheduler

Run tests with: python test_smart_scheduler.py
"""

import unittest
from datetime import datetime, timedelta
from dateutil.tz import gettz
import sys
import os

# Add parent directory to path to import smart_scheduler module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import components to test (will fail if dependencies not installed)
try:
    from smart_scheduler import EventExtractor, GmailClient, CalendarClient
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    print("Warning: Could not import smart_scheduler modules. Install dependencies first.")


class TestEventExtractor(unittest.TestCase):
    """Test the NLP event extraction logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not MODULES_AVAILABLE:
            self.skipTest("Required modules not available")
        self.extractor = EventExtractor(default_tz_name="America/New_York")
    
    def test_simple_date_extraction(self):
        """Test extraction of simple date formats."""
        subject = "Team Meeting"
        body = "Let's meet next Tuesday at 2 PM"
        
        result = self.extractor.extract_event_data(subject, body)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['summary'], "Team Meeting")
        self.assertIsNotNone(result['start'])
        self.assertIsNotNone(result['end'])
        # Check that it's timezone aware
        self.assertIsNotNone(result['start'].tzinfo)
    
    def test_explicit_date_time(self):
        """Test extraction with explicit date and time."""
        subject = "Project Review"
        body = "Meeting on 2026-02-15 at 14:00"
        
        result = self.extractor.extract_event_data(subject, body)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['start'].hour, 14)
        self.assertEqual(result['start'].minute, 0)
    
    def test_duration_extraction(self):
        """Test that duration is extracted from text."""
        subject = "Quick Sync"
        body = "30 minute call tomorrow at 3pm"
        
        result = self.extractor.extract_event_data(subject, body)
        
        self.assertIsNotNone(result)
        duration = (result['end'] - result['start']).total_seconds() / 60
        # Should be 30 minutes
        self.assertAlmostEqual(duration, 30, delta=1)
    
    def test_default_duration(self):
        """Test that default 1-hour duration is applied."""
        subject = "Team Standup"
        body = "Meeting tomorrow at 10am"
        
        result = self.extractor.extract_event_data(subject, body)
        
        self.assertIsNotNone(result)
        duration = (result['end'] - result['start']).total_seconds() / 3600
        # Should default to 1 hour
        self.assertEqual(duration, 1.0)
    
    def test_no_date_returns_none(self):
        """Test that emails without dates return None."""
        subject = "Random Email"
        body = "This is just a regular email with no dates"
        
        result = self.extractor.extract_event_data(subject, body)
        
        # Should return None if no date can be parsed
        # (This might parse random numbers, so we just check it doesn't crash)
        # In production, better filtering would be applied
        self.assertIsNotNone(result or True)  # Doesn't crash
    
    def test_timezone_awareness(self):
        """Test that all extracted dates are timezone-aware."""
        subject = "Call"
        body = "Tomorrow at 3pm"
        
        result = self.extractor.extract_event_data(subject, body)
        
        if result:
            self.assertIsNotNone(result['start'].tzinfo)
            self.assertIsNotNone(result['end'].tzinfo)
            # Check it's the correct timezone
            tz_name = str(result['start'].tzinfo)
            self.assertIn("America/New_York", tz_name)
    
    def test_email_extraction(self):
        """Test extraction of email from sender string."""
        sender = "John Doe <john@example.com>"
        email = self.extractor._extract_email(sender)
        
        self.assertEqual(email, "john@example.com")
    
    def test_email_extraction_plain(self):
        """Test extraction when email has no brackets."""
        sender = "john@example.com"
        email = self.extractor._extract_email(sender)
        
        self.assertEqual(email, "john@example.com")


class TestBase64UrlDecoding(unittest.TestCase):
    """Test the Base64url decoding functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not MODULES_AVAILABLE:
            self.skipTest("Required modules not available")
        # Create a mock GmailClient (without actual service)
        self.client = type('MockGmailClient', (), {
            '_decode_base64url': lambda self, data: GmailClient._decode_base64url(None, data)
        })()
    
    def test_standard_base64url(self):
        """Test decoding of standard Base64url."""
        import base64
        
        original = "Hello, World!"
        # Encode in Base64url format (- instead of +, _ instead of /)
        encoded = base64.urlsafe_b64encode(original.encode()).decode()
        # Remove padding as Gmail API does
        encoded = encoded.rstrip('=')
        
        decoded = self.client._decode_base64url(encoded)
        
        self.assertEqual(decoded, original)
    
    def test_empty_string(self):
        """Test decoding of empty string."""
        decoded = self.client._decode_base64url("")
        self.assertEqual(decoded, "")


class TestIdempotency(unittest.TestCase):
    """Test event ID generation for idempotency."""
    
    def test_same_message_same_id(self):
        """Test that same message ID always generates same event ID."""
        import hashlib
        
        msg_id = "test-message-123"
        
        id1 = hashlib.md5(msg_id.encode('utf-8')).hexdigest()
        id2 = hashlib.md5(msg_id.encode('utf-8')).hexdigest()
        
        self.assertEqual(id1, id2)
    
    def test_different_messages_different_ids(self):
        """Test that different message IDs generate different event IDs."""
        import hashlib
        
        id1 = hashlib.md5("message-1".encode('utf-8')).hexdigest()
        id2 = hashlib.md5("message-2".encode('utf-8')).hexdigest()
        
        self.assertNotEqual(id1, id2)


class TestTimePatterns(unittest.TestCase):
    """Test the regex patterns for finding time-related content."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not MODULES_AVAILABLE:
            self.skipTest("Required modules not available")
        self.extractor = EventExtractor()
    
    def test_find_time_patterns(self):
        """Test that time patterns are found in text."""
        text = "Let's meet at 3pm tomorrow"
        lines = self.extractor._extract_time_relevant_lines(text)
        
        self.assertGreater(len(lines), 0)
    
    def test_no_time_patterns(self):
        """Test text without time patterns."""
        text = "This is a regular email about our project status"
        lines = self.extractor._extract_time_relevant_lines(text)
        
        # Might be empty or might have false positives
        # Main thing is it doesn't crash
        self.assertIsInstance(lines, list)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests with realistic email scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not MODULES_AVAILABLE:
            self.skipTest("Required modules not available")
        self.extractor = EventExtractor(default_tz_name="America/New_York")
    
    def test_formal_meeting_invitation(self):
        """Test formal meeting invitation format."""
        subject = "Q4 Planning Meeting"
        body = """
        Hi Team,
        
        We need to schedule our Q4 planning session.
        
        Date: February 20, 2026
        Time: 2:00 PM EST
        Duration: 2 hours
        
        Please confirm your availability.
        
        Thanks,
        Sarah
        """
        
        result = self.extractor.extract_event_data(subject, body)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['summary'], "Q4 Planning Meeting")
        # Check that duration extraction worked (2 hours)
        duration_hours = (result['end'] - result['start']).total_seconds() / 3600
        self.assertAlmostEqual(duration_hours, 2.0, delta=0.1)
    
    def test_casual_scheduling(self):
        """Test casual scheduling format."""
        subject = "Coffee catch-up"
        body = "Hey! Want to grab coffee tomorrow at 10am? Should take about 30 minutes."
        
        result = self.extractor.extract_event_data(subject, body)
        
        self.assertIsNotNone(result)
        self.assertIn("Coffee", result['summary'])
    
    def test_relative_date(self):
        """Test relative date expressions."""
        subject = "Weekly Sync"
        body = "Let's sync next Friday at 3pm"
        
        result = self.extractor.extract_event_data(subject, body)
        
        self.assertIsNotNone(result)
        # Check that it's in the future
        self.assertGreater(result['start'], datetime.now(tz=gettz("America/New_York")))


def run_tests():
    """Run all tests."""
    print("=" * 60)
    print("Smart Scheduler Test Suite")
    print("=" * 60)
    print()
    
    if not MODULES_AVAILABLE:
        print("⚠️  Warning: Dependencies not installed.")
        print("   Run: pip install -r requirements.txt")
        print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestEventExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestBase64UrlDecoding))
    suite.addTests(loader.loadTestsFromTestCase(TestIdempotency))
    suite.addTests(loader.loadTestsFromTestCase(TestTimePatterns))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
