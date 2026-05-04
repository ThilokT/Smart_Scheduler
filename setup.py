#!/usr/bin/env python3
"""
Smart Scheduler Setup Script

This script helps you set up the Smart Scheduler step-by-step.
"""

import os
import sys
import subprocess

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60 + "\n")

def print_step(number, text):
    """Print a step number."""
    print(f"\n📍 Step {number}: {text}")
    print("-" * 60)

def check_python_version():
    """Check if Python version is 3.8 or higher."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Error: Python 3.8 or higher is required.")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def install_dependencies():
    """Install required Python packages."""
    print("Installing dependencies from requirements.txt...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def check_credentials():
    """Check if credentials.json exists."""
    if os.path.exists("credentials.json"):
        print("✓ credentials.json found")
        return True
    else:
        print("⚠️  credentials.json not found")
        return False

def setup_credentials():
    """Guide user through credential setup."""
    print("\nTo get credentials.json:")
    print("1. Visit: https://console.cloud.google.com/")
    print("2. Create a new project (or select existing)")
    print("3. Enable these APIs:")
    print("   - Gmail API")
    print("   - Google Calendar API")
    print("4. Go to: APIs & Services → Credentials")
    print("5. Create OAuth Client ID")
    print("   - Application type: Desktop App")
    print("   - Download the JSON file")
    print("6. Save it as 'credentials.json' in this directory")
    print()
    
    response = input("Have you completed these steps? (y/n): ").lower()
    return response == 'y'

def run_demo():
    """Ask if user wants to run demo."""
    print("\nThe demo shows how the scheduler works without real credentials.")
    response = input("Would you like to run the demo? (y/n): ").lower()
    
    if response == 'y':
        print("\n" + "=" * 60)
        print("Running demo...")
        print("=" * 60)
        try:
            subprocess.check_call([sys.executable, "demo.py"])
            return True
        except subprocess.CalledProcessError:
            print("❌ Demo failed to run")
            return False
    return True

def run_first_auth():
    """Run the scheduler for first authentication."""
    print("\nRunning Smart Scheduler for first-time authentication...")
    print("A browser window will open. Please:")
    print("1. Sign in to your Google Account")
    print("2. Click 'Allow' to grant permissions")
    print("3. Close the browser tab when complete")
    print()
    
    response = input("Ready to proceed? (y/n): ").lower()
    
    if response == 'y':
        try:
            subprocess.check_call([sys.executable, "smart_scheduler.py"])
            return True
        except subprocess.CalledProcessError:
            print("❌ Authentication failed")
            return False
        except KeyboardInterrupt:
            print("\n⚠️  Setup interrupted by user")
            return False
    return False

def print_next_steps():
    """Print what to do next."""
    print_header("✅ Setup Complete!")
    
    print("You can now use Smart Scheduler with these commands:\n")
    print("📧 Process emails once:")
    print("   python smart_scheduler.py\n")
    print("🔄 Run continuously (daemon mode):")
    print("   python smart_scheduler.py --daemon\n")
    print("🔍 Use custom search query:")
    print("   python smart_scheduler.py --query 'is:unread from:boss@example.com'\n")
    print("🕐 Different timezone:")
    print("   python smart_scheduler.py --timezone 'Europe/London'\n")
    print("📚 For more options:")
    print("   python smart_scheduler.py --help\n")
    print("📖 Read the full documentation:")
    print("   - QUICKSTART.md (quick reference)")
    print("   - README.md (complete guide)")
    print("   - ARCHITECTURE.md (technical details)\n")

def main():
    """Main setup flow."""
    print_header("Smart Scheduler Setup Wizard")
    
    print("This wizard will help you set up the Smart Scheduler.")
    print("It will guide you through:")
    print("  • Installing dependencies")
    print("  • Setting up Google API credentials")
    print("  • Running initial authentication")
    print()
    
    input("Press Enter to begin...")
    
    # Step 1: Check Python version
    print_step(1, "Checking Python Version")
    if not check_python_version():
        sys.exit(1)
    
    # Step 2: Install dependencies
    print_step(2, "Installing Dependencies")
    response = input("Install required packages? (y/n): ").lower()
    if response == 'y':
        if not install_dependencies():
            print("\nYou can install manually with:")
            print("  pip install -r requirements.txt")
            sys.exit(1)
    else:
        print("Skipping dependency installation.")
        print("Note: You'll need to install them manually later.")
    
    # Step 3: Check for credentials
    print_step(3, "Checking for Credentials")
    has_creds = check_credentials()
    
    if not has_creds:
        if not setup_credentials():
            print("\n⚠️  Setup cannot continue without credentials.json")
            print("Please obtain credentials and run setup again.")
            sys.exit(1)
        
        # Re-check after user says they've set it up
        if not check_credentials():
            print("\n⚠️  Still cannot find credentials.json")
            print("Please ensure it's in the current directory and try again.")
            sys.exit(1)
    
    # Step 4: Optional demo
    print_step(4, "Demo (Optional)")
    run_demo()
    
    # Step 5: First authentication
    print_step(5, "First-Time Authentication")
    
    if os.path.exists("token.json"):
        print("✓ token.json already exists (previously authenticated)")
        response = input("Re-authenticate anyway? (y/n): ").lower()
        if response != 'y':
            print_next_steps()
            return
    
    if not run_first_auth():
        print("\n⚠️  Authentication was not completed.")
        print("You can run it manually later with:")
        print("  python smart_scheduler.py")
        sys.exit(1)
    
    # Done!
    print_next_steps()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user.")
        print("You can run this script again anytime.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
