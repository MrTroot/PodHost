import sys
import os
import subprocess
import time
import mimetypes
import re
import json
import spotipy
import shutil
import pytz
from datetime import datetime
from urllib.parse import quote
from spotipy.oauth2 import SpotifyClientCredentials
from threading import Thread
from feedgen.feed import FeedGenerator
from flask import Flask, send_from_directory
from zotify_auth import ZotifyAuth

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

PODCASTS_DIR = os.path.join(DATA_DIR, "podcasts")
if not os.path.exists(PODCASTS_DIR):
    os.makedirs(PODCASTS_DIR)

TEMP_DIR = os.path.join(DATA_DIR, "temp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
ZOTIFY_CREDENTIAL_PATH = os.path.join(DATA_DIR, "zotify_credentials.json")

EASTERN_TIMEZONE = pytz.timezone('US/Eastern')

#Create Flask app
app = Flask(__name__, static_folder=None)

# Update the RSS feed for a given podcast
def update_rss_feed(podcast_id, podcast_data):
    podcast_dir = os.path.join(PODCASTS_DIR, podcast_id)
    podcast_name = podcast_data['name']
    podcast_description = podcast_data['description']
    podcast_cover_url = podcast_data['images'][0]['url']
    podcast_episodes = podcast_data['episodes']['items']

    # Set up the feed generator for this podcast
    fg_podcast = FeedGenerator()
    fg_podcast.load_extension('podcast')
    fg_podcast.id(podcast_id)
    fg_podcast.title(podcast_name)
    fg_podcast.link(href=appurl + podcast_id + "/rss.xml", rel='alternate')
    fg_podcast.description(podcast_description)
    fg_podcast.image(url=podcast_cover_url)

    # Add episodes
    for episode in podcast_episodes:
        episode_id = episode['id']
        episode_name = episode['name']
        episode_description = episode['description']
        episode_published = episode['release_date']
        episode_duration = episode['duration_ms']
        web_path = appurl + podcast_id + "/" + episode_id + ".ogg"

        fe = fg_podcast.add_entry()
        fe.id(episode_id)
        fe.title(episode_name)
        fe.link(href=web_path, rel='alternate')
        fe.description(episode_description)
        episode_published = episode['release_date']
        episode_published = datetime.fromisoformat(episode_published).replace(tzinfo=pytz.UTC).astimezone(EASTERN_TIMEZONE)
        fe.pubDate(episode_published)
        fe.enclosure(url=web_path, length=0, type='audio/ogg')
        fe.podcast.itunes_duration(episode_duration // 1000)

    # Save the feed as an XML file in the subfolder
    fg_podcast.rss_file(os.path.join(podcast_dir, 'rss.xml'), pretty=True)


# Set up the Flask app to serve the RSS feeds
@app.route('/<path:filename>')
def serve_file(filename):
    if not filename:
        return list_feeds()
    print("Serving:", filename)
    content_type, _ = mimetypes.guess_type(filename)
    if filename.endswith('.xml'):
        content_type = 'application/rss+xml'
    return send_from_directory(PODCASTS_DIR, filename, mimetype=content_type)


@app.route('/')
def list_feeds():
    feeds = []
    for podcast in podcasts:
        podcast_id = podcast['id']
        podcast_name = podcast['name']
        rss_url = appurl + podcast_id + "/rss.xml"
        feeds.append({'name': podcast_name, 'rss_url': rss_url})

    html = "<h1>Available RSS Feeds:</h1><ul>"
    for feed in feeds:
        html += f"<li><a href='{feed['rss_url']}'>{feed['name']}</a></li>"
    html += "</ul>"
    return html

#Load config
def load_config(config_file):
    if not os.path.exists(config_file):
        print(f"No config file found at {config_file}. Generating default config...")
        create_default_config(config_file)
        print("Default config file generated. Please update the config file and restart the container.")
        sys.exit(0)

    with open(config_file, 'r') as f:
        config = json.load(f)
        if config['spotify_client_id'] == "your_client_ID":
            print("Default config file generated. Please update the config file and restart the container.")
            sys.exit(0)

    return config

#Create default config
def create_default_config(config_file):
    default_config = {
        "appurl": "http://127.0.0.1/",
        "spotify_client_id": "your_client_ID",
        "spotify_client_secret": "your_client_secret",
        "spotify_username": "your_username",
        "spotify_password": "your_password",
        "podcasts": [
            {
                "name": "Heavyweight",
                "id": "5c26B28vZMN8PG0Nppmn5G"
            }
        ]
    }
    with open(config_file, 'w') as f:
        json.dump(default_config, f, indent=2)

def update_podcasts():
    while True:
        print('Updating podcasts')
        for podcast in podcasts:
            
            
            #Get podcast info from Spotify API
            podcast_id = podcast['id']
            podcast_localdata = get_local_metadata(podcast_id)
            podcast_data = sp.show(podcast_id, market='US')
            
            #Compare our local episode data with the latest from the API. If the count is different, a new episode was released.
            if(podcast_localdata == None or (len(podcast_localdata['episodes']['items']) != len(podcast_data['episodes']['items']))):
                podcast_episodes = podcast_data['episodes']['items']
                podcast_name = podcast_data['name']
                
                print(f'Updating {podcast_name}')
                # Iterate through the episodes
                for episode in podcast_episodes:
                    # Check if the episode has already been downloaded, download if not
                    episode_id = episode['id']
                    episode_name = episode['name']
                    expected_path = os.path.join(os.path.join(PODCASTS_DIR, podcast_id), episode_id + ".ogg")
                    if not os.path.isfile(expected_path):
                        #Download missing episode
                        download_episode(podcast_id, podcast_name, episode)
                
                #After we have downloaded the latest episodes, update the RSS feed
                update_rss_feed(podcast_id, podcast_data)

            #Update local data
            save_local_metadata(podcast_id, podcast_data)

                
        time.sleep(7200)

def download_episode(podcast_id, podcast_name, episode):
    try:
        episode_url = episode['external_urls']['spotify']
        episode_id = episode['id']
        episode_name = episode['name']
        print("Downloading " + episode_url)
        command = ["zotify", f"--credentials-location={ZOTIFY_CREDENTIAL_PATH}", f"--root-podcast-path={TEMP_DIR}", "--print-download-progress=False", "--download-format=ogg",episode_url]
        subprocess.run(command, check=True)
        #Zotify doesnt respect formatting options for podcasts. So we downloaded the file to a temporary directory. We are now going to rename and move it.
        expected_dir = os.path.join(TEMP_DIR, podcast_name)
        expected_name = fix_filename(podcast_name) + ' - ' + fix_filename(episode_name)
        expected_file_path = os.path.join(expected_dir, expected_name + ".ogg")

        if os.path.isfile(expected_file_path):
            #Move and rename file
            new_file_dir = os.path.join(PODCASTS_DIR, podcast_id)
            if not os.path.exists(new_file_dir):
                os.makedirs(new_file_dir)
            new_file_path = os.path.join(new_file_dir, episode_id + ".ogg")
            os.rename(expected_file_path, new_file_path)
        else:
            print("ERROR: Unable to find downloaded file from Zotify for episode " + episode_url)

    except subprocess.CalledProcessError as e:
        print(f"Error downloading files: {e}")


def get_local_metadata(podcast_id):
    podcast_dir = os.path.join(PODCASTS_DIR, podcast_id)
    metadata_path = os.path.join(podcast_dir, "metadata.json")
    if os.path.isfile(metadata_path):
        with open(metadata_path, "r") as f:
            return json.load(f)
    else:
        return None

def save_local_metadata(podcast_id, podcast_data):
    podcast_dir = os.path.join(PODCASTS_DIR, podcast_id)
    metadata_path = os.path.join(podcast_dir, "metadata.json")
    with open(metadata_path, "w") as f:
            json.dump(podcast_data, f, indent=2)   


#Taken from Zotify. This is how it removed invalid characters from file names. Needed to match the correct file after downloading.
def fix_filename(name):
    return re.sub(r'[/\\:|<>"?*\0-\x1f]|^(AUX|COM[1-9]|CON|LPT[1-9]|NUL|PRN)(?![^.])|^\s|[\s.]$', "_", str(name), flags=re.IGNORECASE)

def clear_temp_directory():
    for root, dirs, files in os.walk(TEMP_DIR, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            shutil.rmtree(os.path.join(root, dir))



#Load config
config = load_config(CONFIG_PATH)
appurl = config['appurl']
podcasts = config['podcasts']
spotify_client_id = config['spotify_client_id']
spotify_client_secret = config['spotify_client_secret']
spotify_username = config['spotify_username']
spotify_password = config['spotify_password']

#Get and save token for Zotify auth
if not os.path.isfile(ZOTIFY_CREDENTIAL_PATH):
    ZotifyAuth.login(spotify_username, spotify_password, ZOTIFY_CREDENTIAL_PATH)

#Initiate Spotipy library
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret))

# Clear temp directory
clear_temp_directory()
# Start the update thread
update_thread = Thread(target=update_podcasts)
update_thread.start()

# Start the Flask app
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=80)
