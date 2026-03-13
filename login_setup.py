import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import instaloader
import json
import os
from pathlib import Path
import pickle
import functools
print = functools.partial(print, flush=True)

def load_session_credentials():
    """Load sessionid from config.json"""
    BASE_DIR = Path(__file__).resolve().parent
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        print("config.json not found!")
        print('''Create config.json:
{
  "primary_account": {
    "username": "struberry.__",
    "sessionid": "59342574641%3A9A0STMrxaMrrKI%3A24%3AAYh9YXEImp2DpFp5p9xAt7c9mKckSd8YqOCvrxObMA"
  },
  "target_account": "jade_scythe",
  "monitor_interval_hours": 6
}
        ''')
        exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    username = config['primary_account']['username']
    sessionid = config['primary_account']['sessionid']
    
    if not sessionid or sessionid == "your_sessionid_here":
        print("Please set your real sessionid in config.json")
        exit(1)
    
    return username, sessionid

def setup_session():
    """Create session file using sessionid - FIXED VERSION"""
    username, sessionid = load_session_credentials()
    
    print(f"Setting up session for: {username}")
    print("Session ID loaded (first 20 chars):", sessionid[:20] + "...")
    
    L = instaloader.Instaloader()
    
    try:
        # Manually set cookies with sessionid
        L.context._session.cookies.clear()
        L.context._session.cookies.set('sessionid', sessionid, domain='.instagram.com')
        L.context.username = username
        
        # Test login by fetching profile
        profile = instaloader.Profile.from_username(L.context, username)
        print(f"Session verified! Profile: {profile.full_name}")
        print(f"Followers: {profile.followers}")
        
        # Save session using pickle (fixed method)
        session_file = f"session-{username}"
        with open(session_file, 'wb') as f:
            pickle.dump(L.context._session, f)
        
        print(f"Session file created: {session_file}")
        print("Ready! Run: python instagram_monitor.py")
        print("Done")
        
    except Exception as e:
        print(f"Session setup failed: {e}")
        print("1. Make sure you're logged into instagram.com")
        print("2. Refresh sessionid from browser cookies")
        print("3. Update config.json and try again")

if __name__ == "__main__":
    setup_session()