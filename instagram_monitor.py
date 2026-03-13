import instaloader
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import time
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Tuple
from instaloader import Post
import functools
print = functools.partial(print, flush=True)

class InstagramMonitor:
    def log(self, message):
        print(message)

    def __init__(self, config_path: str = 'config.json'):
        self.verbose = False
        self.config = self.load_config(config_path)
        self.primary_username = self.config['primary_account']['username']
        self.session_file = f"session-{self.primary_username}"
        
        self.L = instaloader.Instaloader(
            dirname_pattern='data/{target}',
            filename_pattern='{target}_{date_utc}_UTCs{shortcode}',
            quiet=True,
            request_timeout=60,
            max_connection_attempts=3
        )
        
        # disable instaloader internal logs
        self.L.context.log = lambda *args, **kwargs: None
        self.L.context.error = lambda *args, **kwargs: None
        
        # Load saved session
        if os.path.exists(self.session_file):
            self.load_session()
            self.log("Session loaded")
        else:
            print(f"No session file: {self.session_file}")
            print("Run: python login_setup.py first")
            exit(1)
            
        self.target_username = self.config['target_account']
        self.data_dir = f"monitor_data/{self.target_username}"
        self.ensure_dirs()
    
    def load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON"""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"config.json not found!")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        sessionid = os.getenv("SESSION_ID") or config['primary_account']['sessionid']
        
        if not sessionid or len(sessionid) < 10:
            raise ValueError("Invalid sessionid in config.json")
        return config
    
    def load_session(self):
        """Load session from pickle file"""
        try:
            with open(self.session_file, 'rb') as f:
                session = pickle.load(f)
            self.L.context._session = session
            self.L.context.username = self.primary_username
        except Exception as e:
            raise Exception(f"Failed to load session: {e}")
    
    def ensure_dirs(self):
        """Create necessary directories"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs('data', exist_ok=True)
    
    def fetch_user_details(self, usernames):
        """Fetch minimal profile details for a list of usernames"""
        details = []
        for username in usernames:
            try:
                profile = instaloader.Profile.from_username(self.L.context, username)
                details.append({
                    "userid": profile.userid,
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "profile_pic_url": profile.profile_pic_url
                })
            except Exception:
                details.append({
                    "username": username
                })
        return details
    
    def fetch_post_details(self, shortcodes):
        """Fetch minimal details for posts"""
        posts = []
        for code in shortcodes:
            try:
                post = Post.from_shortcode(self.L.context, code)
                posts.append({
                    "shortcode": post.shortcode,
                    "caption": post.caption,
                    "likes": post.likes,
                    "comments": post.comments,
                    "timestamp": post.date_utc.isoformat(),
                    "url": f"https://www.instagram.com/p/{post.shortcode}/"
                })
            except Exception:
                posts.append({"shortcode": code})
        return posts

    def serialize_user(self, user):
        """Convert Instaloader Profile object to JSON-safe dict"""
        try:
            return {
                "userid": user.userid,
                "username": user.username,
                "full_name": user.full_name,
                "is_verified": user.is_verified,
                "profile_pic_url": user.profile_pic_url
            }
        except Exception:
            return {"username": user.username}

    def get_profile(self) -> instaloader.Profile:
        """Get target profile object"""
        profile = instaloader.Profile.from_username(self.L.context, self.target_username)
        self.log(f"Target: @{profile.username}")
        return profile
    
    def get_profile_metadata(self, profile):
        """Capture profile metadata snapshot"""
        return {
            "username": profile.username,
            "userid": profile.userid,
            "full_name": profile.full_name,
            "bio": profile.biography,
            "followers": profile.followers,
            "following": profile.followees,
            "posts": profile.mediacount,
            "is_private": profile.is_private,
            "is_verified": profile.is_verified,
            "profile_pic": profile.profile_pic_url
        }

    def load_previous_data(self) -> Tuple[Set[str], Set[str]]:
        """Load previous followers/following from cache"""
        followers_file = os.path.join(self.data_dir, 'followers.json')
        following_file = os.path.join(self.data_dir, 'following.json')
        
        prev_followers = set()
        prev_following = set()            
        posts_file = os.path.join(self.data_dir, 'posts.json')
        prev_posts = set()
        
        if os.path.exists(followers_file):
            with open(followers_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    prev_followers = set(u["username"] for u in data)
                else:
                    prev_followers = set(data)

        if os.path.exists(following_file):
            with open(following_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    prev_following = set(u["username"] for u in data)
                else:
                    prev_following = set(data)
        
        if os.path.exists(posts_file):
            with open(posts_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    prev_posts = set(data)
                else:
                    prev_posts = set()
            
        return prev_followers, prev_following, prev_posts
    
    def save_current_data(self, followers, following, posts, profile_meta):
        with open(os.path.join(self.data_dir, 'followers.json'), 'w') as f:
            json.dump(list(followers), f)
        with open(os.path.join(self.data_dir, 'following.json'), 'w') as f:
            json.dump(list(following), f)
        with open(os.path.join(self.data_dir, 'posts.json'), 'w') as f:
            json.dump(list(posts), f)
        with open(os.path.join(self.data_dir, 'profile.json'), 'w') as f:
            json.dump(profile_meta, f, indent=2)
    
    def get_followers(self, profile):
        print("Fetching followers...")
        followers = set()
        count = 0
        try:
            for user in profile.get_followers():
                followers.add(user.username)
                count += 1
                # show live progress
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Fetching followers [{count}]", flush=True)
        except Exception as e:
            self.log(f"Follower fetch limited: {e}")
        return followers
    
    def get_following(self, profile):
        print("Fetching following...")
        following = set()
        count = 0
        try:
            for user in profile.get_followees():
                following.add(user.username)
                count += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Fetching followers [{count}]", flush=True)
        except Exception as e:
            self.log(f"Following fetch limited: {e}")
        return following
    
    def get_posts(self, profile):
        print("Fetching posts...")
        posts = set()
        count = 0
        try:
            for post in profile.get_posts():
                posts.add(post.shortcode)
                count += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Fetching posts [{count}]", flush=True)
        except Exception:
            pass
        return posts

    def analyze_changes(self,
                    prev_followers, curr_followers,
                    prev_following, curr_following,
                    prev_posts, curr_posts):
        
        new_followers = curr_followers - prev_followers
        lost_followers = prev_followers - curr_followers
        new_following = curr_following - prev_following
        unfollowed = prev_following - curr_following
        
        new_posts = curr_posts - prev_posts
        deleted_posts = prev_posts - curr_posts

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("\nChanges detected:")
        print(f"Followers +{len(new_followers)}  -{len(lost_followers)}")
        print(f"Following +{len(new_following)}  -{len(unfollowed)}")
        print(f"Posts +{len(new_posts)}  -{len(deleted_posts)}")

        # Fetch details ONLY for changed users
        new_followers_details = self.fetch_user_details(new_followers)
        lost_followers_details = self.fetch_user_details(lost_followers)
        new_following_details = self.fetch_user_details(new_following)
        unfollowed_details = self.fetch_user_details(unfollowed)
        new_posts_details = self.fetch_post_details(new_posts)
        deleted_posts_details = self.fetch_post_details(deleted_posts)

        report = {
            "date": timestamp,
            "new_followers": new_followers_details,
            "lost_followers": lost_followers_details,
            "new_following": new_following_details,
            "unfollowed": unfollowed_details,
            "new_posts": new_posts_details,
            "deleted_posts": deleted_posts_details
        }
        report_file = os.path.join(self.data_dir, "daily_change_report.json")

        # detect if current run has changes
        changes_exist = (
            len(new_followers) > 0 or
            len(lost_followers) > 0 or
            len(new_following) > 0 or
            len(unfollowed) > 0 or
            len(new_posts) > 0 or
            len(deleted_posts) > 0
        )

        # load previous report
        previous = None
        if os.path.exists(report_file):
            try:
                with open(report_file, "r") as f:
                    previous = json.load(f)
            except Exception:
                previous = None

        # detect if previous report had changes
        previous_had_changes = False
        if isinstance(previous, dict):
            previous_had_changes = (
                previous.get("new_followers") or
                previous.get("lost_followers") or
                previous.get("new_following") or
                previous.get("unfollowed") or
                previous.get("new_posts") or
                previous.get("deleted_posts")
            )

        # logic
        if changes_exist and previous_had_changes:
            history = []
            if isinstance(previous, list):
                history = previous
            elif isinstance(previous, dict):
                history = [previous]

            history.append(report)

            with open(report_file, "w") as f:
                json.dump(history, f, indent=2)

        else:
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
            
        self.log("Daily report saved")

        return {
            "new_followers": len(new_followers),
            "lost_followers": len(lost_followers),
            "new_following": len(new_following),
            "unfollowed": len(unfollowed)
        }
    
    def run_monitor(self):
        """Run complete monitoring cycle"""
        try:
            profile = self.get_profile()

            prev_followers, prev_following, prev_posts = self.load_previous_data()
            
            print("\nPrevious:")
            print(f"followers: {len(prev_followers)} | followings: {len(prev_following)} | posts: {len(prev_posts)}\n")
            
            curr_followers = self.get_followers(profile)
            curr_following = self.get_following(profile)
            curr_posts = self.get_posts(profile)
            
            profile_meta = self.get_profile_metadata(profile)
            
            self.save_current_data(curr_followers, curr_following, curr_posts, profile_meta)
            
            if prev_followers or prev_following or prev_posts:
                changes = self.analyze_changes(
                    prev_followers, curr_followers,
                    prev_following, curr_following,
                    prev_posts, curr_posts
                )
            else:
                print("\nFirst run - baseline data created!")
            
            print(f"\nAll data: monitor_data/{self.target_username}/")
            print("Done")
            return True

        except Exception as e:
            print(f"Monitor failed: {e}")
            print("Done")
            return False

def main():
    monitor = InstagramMonitor()
    success = monitor.run_monitor()
    if success:
        print("Monitor completed successfully")
    else:
        print("Monitor failed")

if __name__ == "__main__":
    main()