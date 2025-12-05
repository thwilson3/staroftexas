import requests
import requests_cache
import streamlit as st
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timedelta
from pathlib import Path

#expire cach after 1 hour
requests_cache.install_cache('cache', expire_after=3600)

TRACKING_FILE = Path('/Users/tommywilson/personal_projects/staroftexas/artist_tracking.json')
LAUNCH_DATE = datetime(2025, 12, 6)

def load_tracking_data():
    if TRACKING_FILE.exists():
        try:
            with open(TRACKING_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_tracking_data(data):
    with open(TRACKING_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def is_new_artist(handle, tracking_data, days_threshold=14):
    if handle not in tracking_data:
        return True
    first_seen = datetime.fromisoformat(tracking_data[handle])

    if first_seen < LAUNCH_DATE:
        return False

    days_ago = (datetime.now() - first_seen).days
    return first_seen.strftime('%m/%d/%Y') != '12/05/2025' or days_ago <= days_threshold

# Specify the URL of the page to scrape
url = "https://golivefast.com/exhibitorsaus.php"
response = requests.get(url)

formatted_links = {}

st.title("Star of Texas Artist List")

if response.status_code == 200:
    tracking_data = load_tracking_data()
    current_artists = set()
    new_artists = []
    artists_to_display = []  # NEW: Store artists for later display

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')
    artist_divs = soup.find_all('div', class_='artist')

    # STEP 1: Collect all the data first (no displaying yet)
    for artist_div in artist_divs:
        for a in artist_div.find_all('a', href=True):
            link = a['href']
            parsed_link = urlparse(link)
            if parsed_link.path.endswith('/'):
                new_path = parsed_link.path[:-1]
                parsed_link = parsed_link._replace(path=new_path)
            handle = parsed_link.path.split('/')[-1]

            if 'instagram' in link and handle:
                if handle not in tracking_data:
                    tracking_data[handle] = datetime.now().isoformat()
                    new_artists.append(handle)

                current_artists.add(handle)
                is_new = is_new_artist(handle, tracking_data)

                # Store for later display
                artists_to_display.append({
                    'handle': handle,
                    'link': link,
                    'is_new': is_new
                })

                formatted_links[handle] = link

    save_tracking_data(tracking_data)

    # STEP 2: Display stats at the top
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Artists", len(current_artists))
    with col2:
        new_count = sum(1 for artist in artists_to_display if artist['is_new'])
        st.metric("New (Last 14 Days)", new_count)

    if new_artists:
        st.info(f"Found {len(new_artists)} brand new artists this check: {', '.join(new_artists)}")

    st.divider()

    filter_option = st.radio(
        "Filter Artists:",
        ('All Artists', 'New Artists Only'),
        horizontal=True
    )

    artists_to_display.sort(key=lambda artist: artist['handle'].lower())

    for artist in artists_to_display:
        should_show = (
            filter_option == 'All Artists' or
            (filter_option == 'New Artists Only' and artist['is_new'])
        )

        if should_show:
            if artist['is_new']:
                st.page_link(artist['link'], label=artist['handle'], icon='🚨')
            else:
                st.page_link(artist['link'], label=artist['handle'])


#     # Print for debugging
#     print("Extracted Links:")
#     print(formatted_links)
# else:
#     st.error(f"Failed to retrieve the page. Status code: {response.status_code}")


