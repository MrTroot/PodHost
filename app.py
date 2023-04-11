import sys
import os
import subprocess
import time
import re
import json
import spotipy
import shutil
import pytz
import hashlib
import config
from flaskapp import start_flask_app
from datetime import datetime
from spotipy.oauth2 import SpotifyClientCredentials
from threading import Thread
from feedgen.feed import FeedGenerator
from zotify_auth import ZotifyAuth

#Execute main loop to update podcasts
def update_podcasts():
    while True:
        print('Updating podcasts')
        for podcast in config.podcasts:
            
            #Get podcast info from Spotify API
            podcast_id = podcast['id']
            podcast_localmetadata = get_local_metadata(podcast_id)
            podcast_info = sp.show(podcast_id, market='US')
            podcast_name = podcast_info['name']

            print(f'Updating {podcast_name}')
            
            #Compare our local episode data with the latest from the API. If the count is different, a new episode was released.
            if(podcast_localmetadata == None or (podcast_localmetadata['total_episodes'] != podcast_info['total_episodes'])):
                
                print(f'New episode(s) found for {podcast_name}')

                #Get podcast episodes by iterating over all pages of results (API limit is 50)
                results = sp.show_episodes(podcast_id, limit=50, market='US')
                podcast_episodes = results['items']
                while results['next']:
                    results = sp.next(results)
                    podcast_episodes.extend(results['items'])
                
                # Iterate through the episodes
                for episode in podcast_episodes:
                    # Check if the episode has already been downloaded, download if not
                    episode_id = episode['id']
                    episode_name = episode['name']
                    expected_path = os.path.join(os.path.join(config.PODCASTS_DIR, podcast_id), episode_id + ".ogg")
                    if not os.path.isfile(expected_path):
                        #Download missing episode
                        download_episode(podcast_id, podcast_name, episode)
                
                #After we have downloaded the latest episodes, update the RSS feed
                update_rss_feed(podcast_id, podcast_info, podcast_episodes)

            #Update local data
            save_local_metadata(podcast_id, podcast_info)

        time.sleep(7200)


# Update the RSS feed for a given podcast
def update_rss_feed(podcast_id, podcast_info, podcast_episodes):

    podcast_name = podcast_info['name']
    podcast_description = podcast_info['description']
    podcast_cover_url = podcast_info['images'][0]['url']

    # Set up the feed generator for this podcast
    fg_podcast = FeedGenerator()
    fg_podcast.load_extension('podcast')
    fg_podcast.id(podcast_id)
    fg_podcast.title(podcast_name)
    fg_podcast.link(href=config.appurl + podcast_id + "/rss.xml", rel='alternate')
    fg_podcast.description(podcast_description)
    fg_podcast.image(url=podcast_cover_url)

    # Add episodes
    for episode in podcast_episodes:
        episode_id = episode['id']
        episode_name = episode['name']
        episode_description = episode['description']
        episode_published = episode['release_date']
        episode_duration = episode['duration_ms']
        web_path = config.appurl + podcast_id + "/" + episode_id + ".ogg"

        fe = fg_podcast.add_entry()
        fe.id(episode_id)
        fe.title(episode_name)
        fe.link(href=web_path, rel='alternate')
        fe.description(episode_description)
        episode_published = episode['release_date']
        episode_published = datetime.fromisoformat(episode_published).replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('US/Eastern'))
        fe.pubDate(episode_published)
        fe.enclosure(url=web_path, length=0, type='audio/ogg')
        fe.podcast.itunes_duration(episode_duration // 1000)

    # Save the feed as an XML file in the subfolder
    fg_podcast.rss_file(os.path.join(get_podcast_dir(podcast_id), 'rss.xml'), pretty=True)


#Downloads a given episode of a podcast
def download_episode(podcast_id, podcast_name, episode):
    try:
        episode_url = episode['external_urls']['spotify']
        episode_id = episode['id']
        episode_name = episode['name']
        print("Downloading " + episode_url)
        command = ["zotify", f"--credentials-location={config.ZOTIFY_CREDENTIAL_PATH}", f"--root-podcast-path={config.TEMP_DIR}", "--print-download-progress=False", "--download-format=ogg",episode_url]
        subprocess.run(command, check=True)
        #Zotify doesnt respect formatting options for podcasts. So we downloaded the file to a temporary directory. We are now going to rename and move it.
        expected_dir = os.path.join(config.TEMP_DIR, podcast_name)
        expected_name = fix_filename(podcast_name) + ' - ' + fix_filename(episode_name)
        expected_file_path = os.path.join(expected_dir, expected_name + ".ogg")

        if os.path.isfile(expected_file_path):
            #Move and rename file
            new_file_dir = os.path.join(config.PODCASTS_DIR, podcast_id)
            if not os.path.exists(new_file_dir):
                os.makedirs(new_file_dir)
            new_file_path = os.path.join(new_file_dir, episode_id + ".ogg")
            os.rename(expected_file_path, new_file_path)
        else:
            print("ERROR: Unable to find downloaded file from Zotify for episode " + episode_url)

    except subprocess.CalledProcessError as e:
        print(f"Error downloading files: {e}")


#Gets the directory for a given podcast
def get_podcast_dir(podcast_id):
    return os.path.join(config.PODCASTS_DIR, podcast_id)


def get_local_metadata(podcast_id):
    metadata_path = os.path.join(get_podcast_dir(podcast_id), "metadata.json")
    if os.path.isfile(metadata_path):
        with open(metadata_path, "r") as f:
            return json.load(f)
    else:
        return None


def save_local_metadata(podcast_id, podcast_data):
    metadata_path = os.path.join(get_podcast_dir(podcast_id), "metadata.json")
    with open(metadata_path, "w") as f:
            json.dump(podcast_data, f, indent=2)   


#Taken from Zotify. This is how it removed invalid characters from file names. Needed to match the correct file after downloading.
def fix_filename(name):
    return re.sub(r'[/\\:|<>"?*\0-\x1f]|^(AUX|COM[1-9]|CON|LPT[1-9]|NUL|PRN)(?![^.])|^\s|[\s.]$', "_", str(name), flags=re.IGNORECASE)


#Clear the temporary download directory
def clear_temp_directory():
    for root, dirs, files in os.walk(config.TEMP_DIR, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            shutil.rmtree(os.path.join(root, dir))

#Get and save token for Zotify auth
if not os.path.isfile(config.ZOTIFY_CREDENTIAL_PATH):
    ZotifyAuth.login(config.spotify_username, config.spotify_password, config.ZOTIFY_CREDENTIAL_PATH)



#Initiate Spotipy library
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=config.spotify_client_id, client_secret=config.spotify_client_secret))

# Clear temp directory
clear_temp_directory()

#Start the flask app
web_thread = Thread(target=start_flask_app)
web_thread.start()

#Start the update thread
update_thread = Thread(target=update_podcasts)
update_thread.start()