from playwright.sync_api import sync_playwright
import json
import datetime
import os
import spotipy
import requests
import base64

URL = "https://www.siriusxm.com/channels/octane"
JSON_FILE = "octane_history.json"

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SPOTIFY_PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID")

def get_spotify_client():
    if not all([SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN]):
        print("Spotify credentials missing. Skipping Spotify integration.")
        return None
        
    # The .strip() removes any accidental spaces or newlines from your GitHub Secrets
    clean_client_id = SPOTIFY_CLIENT_ID.strip()
    clean_secret = SPOTIFY_CLIENT_SECRET.strip()
    clean_token = SPOTIFY_REFRESH_TOKEN.strip()
        
    auth_str = f"{clean_client_id}:{clean_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": clean_token
    }
    
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    
    if response.status_code != 200:
        print(f"Spotify Token Exchange Failed (Status {response.status_code})")
        print(f"Spotify's exact error message: {response.text}")
        return None
        
    access_token = response.json()["access_token"]
    
    return spotipy.Spotify(auth=access_token)

def add_to_spotify(sp, artist, song):
    if not sp: return
    
    # Search Spotify for the track
    query = f"artist:{artist} track:{song}"
    results = sp.search(q=query, type='track', limit=1)
    
    if results['tracks']['items']:
        track_uri = results['tracks']['items'][0]['uri']
        try:
            sp.playlist_add_items(SPOTIFY_PLAYLIST_ID, [track_uri])
            print(f"Added to Spotify: {track_uri}")
        except Exception as e:
            print(f"Failed to add to playlist: {e}")
    else:
        print(f"Could not find '{song}' by '{artist}' on Spotify.")

def scrape_song_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print("Fetching...")
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            
            selector = '[class^="staticChannelCard_radioTextInfo"]'
            page.wait_for_selector(selector, timeout=15000)
            
            now_playing_text = page.locator(selector).first.inner_text().strip()
            parts = [line.strip() for line in now_playing_text.split('\n') if line.strip()]
            
            if len(parts) >= 2:
                song = parts[0]
                artist = parts[1]
            else:
                print("Couldn't get track text.")
                return
            
            if os.path.exists(JSON_FILE):
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    try:
                        history = json.load(f)
                    except json.JSONDecodeError:
                        history = []
            else:
                history = []
            
            is_duplicate = any(
                entry.get("artist") == artist and entry.get("song") == song
                for entry in history
            )
            
            if is_duplicate:
                print(f"Skipped: '{song}' by '{artist}' is already in the database.")
                return 
            
            # It's a new song!
            data_entry = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "song": song,
                "artist": artist
            }
                
            history.append(data_entry)
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
                
            print(f"Success: Logged NEW song '{song}' by '{artist}'")
            
            # --- ADD TO SPOTIFY ---
            sp = get_spotify_client()
            add_to_spotify(sp, artist, song)
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    scrape_song_data()
