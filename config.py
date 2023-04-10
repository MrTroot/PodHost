import os
import json
import sys

DATA_DIR = "/data"
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


config = load_config(CONFIG_PATH)
appurl = config['appurl']
podcasts = config['podcasts']
spotify_client_id = config['spotify_client_id']
spotify_client_secret = config['spotify_client_secret']
spotify_username = config['spotify_username']
spotify_password = config['spotify_password']