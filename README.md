# PodHost

PodHost is a simple application that generates and hosts RSS feeds for Spotify podcasts, allowing users to subscribe to them using their favorite podcast players. The app is built using Flask, Spotipy, and Zotify.

PodHost is designed to run in a Docker container.

## Running the Application

Pull the Docker container:

```bash
docker pull ghcr.io/mrtroot/podhost:latest
```

Start the PodHost container using the following command:

```bash
docker run -d -p 80:80 -v /path/to/data:/data --name podhost ghcr.io/mrtroot/podhost:latest
```

Replace `/path/to/data` with the desired path to the `data` directory.

When the container first runs, it will generate a default config file.

Once the container is running, you can access the list of available RSS feeds at the configured app URL.

## Configuration

The `config.json` file contains the following fields:

- `appurl`: The public URL where the application will be accessible. This will also be used for the RSS audio file download URLs.
- `spotify_client_id`: Your Spotify client ID. Get this by creating an app at https://developer.spotify.com/dashboard
- `spotify_client_secret`: Your Spotify client secret.
- `spotify_username`: Your Spotify username.
- `spotify_password`: Your Spotify password.
- `podcasts`: A list of podcast objects, each containing a `name` and `id`. The `id` should be the Spotify ID of the podcast. You can find this at the end of the URL for the podcast on the Spotify website.
