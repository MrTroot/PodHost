import sys
import os
import subprocess
import time
import mimetypes
import re
import json
import spotipy
from urllib.parse import quote
from spotipy.oauth2 import SpotifyClientCredentials
from threading import Thread
from feedgen.feed import FeedGenerator
from flask import Flask, send_from_directory

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

PODCAST_DIR = os.path.join(DATA_DIR, "podcasts")
if not os.path.exists(PODCAST_DIR):
    os.makedirs(PODCAST_DIR)

TEMP_DIR = os.path.join(DATA_DIR, "temp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
CREDENTIAL_PATH = os.path.join(DATA_DIR, "credentials.json")

#Create Flask app
app = Flask(__name__, static_folder=None)

# Define a function to scan the folders and generate the RSS feeds
def scan_folders():
    while True:
        # Loop through all the podcast subfolders and generate an RSS feed for each one
        for podcast_path in os.listdir(PODCAST_DIR):
            podcast_localpath = os.path.join(PODCAST_DIR, podcast_path)
            if os.path.isdir(podcast_localpath):
                podcast_webpath = podcast_path
                generate_rss_feed(podcast_webpath, podcast_localpath)

        # Wait for the next scan interval
        time.sleep(300)  # 5 minutes

# Define a function to generate an RSS feed for a given podcast subfolder
def generate_rss_feed(podcast_webpath, podcast_localpath):
    # Set up the feed generator for this podcast
    fg_podcast = FeedGenerator()
    fg_podcast.id(appurl + podcast_webpath)
    fg_podcast.title(podcast_webpath)
    fg_podcast.link(href=appurl + podcast_webpath, rel='alternate')
    fg_podcast.description('Episodes for ' + podcast_webpath)

    # Loop through all the episode files in this subfolder and add them to the feed
    for filename in os.listdir(podcast_localpath):
        if filename.endswith('.mp3') or filename.endswith('.ogg'):
            fe = fg_podcast.add_entry()
            fe.id(appurl + podcast_webpath + '/' + filename)
            fe.title(re.search('(.+)\..+',filename).group(1))
            download_url = quote((appurl + podcast_webpath + '/' + filename).replace(' ', '%20'), safe=':/?&=')
            fe.link(href=download_url, rel='alternate')
            fe.description('Episode for ' + podcast_webpath)

    # Save the feed as an XML file in the subfolder
    fg_podcast.rss_file(podcast_localpath + '/rss.xml', pretty=True)

# Set up the Flask app to serve the RSS feeds
@app.route('/<path:filename>')
def serve_file(filename):
    print("Serving:", filename)
    content_type, _ = mimetypes.guess_type(filename)
    if filename.endswith('.xml'):
        content_type = 'application/rss+xml'
    return send_from_directory(PODCAST_DIR, filename, mimetype=content_type)


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
            podcast_info = sp.show(podcast_id, market='US')
            podcast_episodes = podcast_info['episodes']['items']
            podcast_name = podcast_info['name']
            print(f'Updating {podcast_name}')
            # Iterate through the episodes
            for episode in podcast_episodes:
                # Check if the episode has already been downloaded, download if not
                episode_id = episode['id']
                episode_name = episode['name']
                expected_path = os.path.join(PODCAST_DIR, podcast_name)
                expected_name = fix_filename(podcast_name) + ' - ' + fix_filename(episode_name)
                if not file_exists_without_extension(expected_name, expected_path):
                    #Download episode
                    download_episode(podcast_name, episode)
                
        time.sleep(3600)

def download_episode(podcast_name, episode):
    try:
        episode_url = episode['external_urls']['spotify']
        episode_name = episode['name']
        print("Downloading " + episode_url)
        command = ["zotify", f"--credentials-location={CREDENTIAL_PATH}", f"--root-podcast-path={PODCAST_DIR}", f"--temp-download-dir={TEMP_DIR}", "--print-download-progress=False",episode_url]
        subprocess.run(command, check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error downloading files: {e}")


def file_exists_without_extension(filename_without_extension, directory):
    for file in os.listdir(directory):
        if file.startswith(filename_without_extension):
            return True
    return False

def fix_filename(name):
    return re.sub(r'[/\\:|<>"?*\0-\x1f]|^(AUX|COM[1-9]|CON|LPT[1-9]|NUL|PRN)(?![^.])|^\s|[\s.]$', "_", str(name), flags=re.IGNORECASE)


#Load config
config = load_config(CONFIG_PATH)
appurl = config['appurl']
podcasts = config['podcasts']
spotify_client_id = config['spotify_client_id']
spotify_client_secret = config['spotify_client_secret']

#Initiate Spotipy
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret))

# Start the folder scanning thread
t = Thread(target=scan_folders)
t.start()

# Start the downloading thread
download_thread = Thread(target=update_podcasts)
download_thread.start()

# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
