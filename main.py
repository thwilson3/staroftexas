import requests
import requests_cache
import streamlit as st
from streamlit.components.v1 import declare_component
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

#expire cach after 1 hour
# requests_cache.install_cache('cache', expire_after=3600)

EVENT_YEAR = 2026
TRACKING_FILE = Path(__file__).with_name(f'artist_tracking_{EVENT_YEAR}.json')
BOOKMARKS_FILE = Path(__file__).with_name('artist_bookmarks.json')
PROFILES = {'person_1': 'SMOOCH 🧝‍♀️', 'person_2': 'SMOOCH 🧙‍♂️'}


@st.cache_resource
def data_lock():
    return Lock()

def load_json(path):
    try:
        with path.open() as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_json(path, data):
    with NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        temporary_path = Path(f.name)
        try:
            json.dump(data, f, indent=4)
            f.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)

def set_bookmark(profile, handle, link, saved):
    with data_lock():
        bookmarks = load_json(BOOKMARKS_FILE)
        profile_bookmarks = bookmarks.setdefault(profile, {})
        if saved:
            profile_bookmarks[handle] = link
        else:
            profile_bookmarks.pop(handle, None)
        save_json(BOOKMARKS_FILE, bookmarks)

def is_new_artist(handle, tracking_data, days_threshold=14):
    first_seen = tracking_data.get(handle)
    if first_seen is None:
        return False

    age = datetime.now() - datetime.fromisoformat(first_seen)
    return age <= timedelta(days=days_threshold)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_artist_links():
    response = requests.get("https://golivefast.com/exhibitorsaus.php", timeout=10)
    response.raise_for_status()
    formatted_links = {}
    soup = BeautifulSoup(response.text, 'html.parser')
    artist_divs = soup.find_all('div', class_='artist')

    for artist_div in artist_divs:
        for a in artist_div.find_all('a', href=True):
            link = a['href']
            parsed_link = urlparse(link)
            if parsed_link.path.endswith('/'):
                new_path = parsed_link.path[:-1]
                parsed_link = parsed_link._replace(path=new_path)
            handle = parsed_link.path.split('/')[-1]

            if 'instagram' in link and handle:
                formatted_links.setdefault(handle.lower(), link)

    return formatted_links


pick_profile = declare_component(
    'profile_picker', path=str(Path(__file__).with_name('profile_picker'))
)

st.title("Star of Texas Artist List")
profile = pick_profile(profiles=PROFILES, key="bookmark_profile")
if profile not in PROFILES:
    profile = None
bookmarks = load_json(BOOKMARKS_FILE).get(profile, {})

tracking_data = {}
new_artists = []
artists_to_display = []

try:
    formatted_links = fetch_artist_links()
except requests.RequestException:
    formatted_links = {}
    st.warning("The exhibitor list is unavailable. Your saved bookmarks are still accessible.")
    filter_option = 'Bookmarked Artists'
else:
    with data_lock():
        tracking_data = load_json(TRACKING_FILE)
        baseline = not tracking_data
        unseen_handles = formatted_links.keys() - tracking_data.keys()
        if unseen_handles:
            first_seen = None if baseline else datetime.now().isoformat()
            tracking_data.update(dict.fromkeys(unseen_handles, first_seen))
            save_json(TRACKING_FILE, tracking_data)
            if not baseline:
                new_artists = sorted(unseen_handles)

    for handle, link in formatted_links.items():
        artists_to_display.append({
            'handle': handle,
            'link': link,
            'is_new': is_new_artist(handle, tracking_data)
        })

    col1, col2 = st.columns(2)
    col1.metric("Total Artists", len(formatted_links))
    col2.metric("New (Last 14 Days)", sum(artist['is_new'] for artist in artists_to_display))

    if new_artists:
        st.info(f"Found {len(new_artists)} brand new artists this check: {', '.join(new_artists)}")

    filter_option = st.radio(
        "Filter Artists",
        ('All Artists', 'New Artists Only', 'Bookmarked Artists'),
        horizontal=True
    )

if filter_option == 'Bookmarked Artists':
    if profile is None:
        st.info("Select a bookmark profile to see saved artists.")
    elif not bookmarks:
        st.info("You haven’t bookmarked any artists yet.")
    artists_to_display = [
        {
            'handle': handle,
            'link': formatted_links.get(handle, link),
            'is_new': handle in formatted_links and is_new_artist(handle, tracking_data)
        }
        for handle, link in bookmarks.items()
    ]
elif filter_option == 'New Artists Only':
    artists_to_display = [artist for artist in artists_to_display if artist['is_new']]

search = st.text_input("Search Instagram handles").strip().lstrip("@").lower()
if search:
    artists_to_display = [artist for artist in artists_to_display if search in artist['handle']]
    if not artists_to_display:
        st.info("No artists match your search.")

for artist in sorted(artists_to_display, key=lambda artist: artist['handle']):
    handle = artist['handle']
    artist_column, bookmark_column = st.columns([3, 2])
    with artist_column:
        if artist['is_new']:
            st.page_link(artist['link'], label=handle, icon='🚨')
        else:
            st.page_link(artist['link'], label=handle)
    if profile is not None:
        saved = handle in bookmarks
        bookmark_column.button(
            'Remove bookmark' if saved else 'Bookmark',
            key=f'bookmark:{profile}:{handle}',
            on_click=set_bookmark,
            args=(profile, handle, artist['link'], not saved)
        )
