from flask import Flask, send_from_directory
import mimetypes
import config

#Create Flask app
flask_instance = Flask(__name__, static_folder=None)

# Set up the Flask app to serve the RSS feeds
@flask_instance.route('/<path:filename>')
def serve_file(filename):
    if not filename:
        return list_feeds()
    print("Serving:", filename)
    content_type, _ = mimetypes.guess_type(filename)
    if filename.endswith('.xml'):
        content_type = 'application/rss+xml'
    return send_from_directory(config.PODCASTS_DIR, filename, mimetype=content_type)

# Serve RSS feed list
@flask_instance.route('/')
def list_feeds():
    feeds = []
    for podcast in config.podcasts:
        podcast_id = podcast['id']
        podcast_name = podcast['name']
        rss_url = config.appurl + podcast_id + "/rss.xml"
        feeds.append({'name': podcast_name, 'rss_url': rss_url})

    # HTML with inline CSS
    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }

        h1 {
            font-size: 36px;
            margin-bottom: 20px;
        }

        ul {
            list-style-type: none;
            padding: 0;
        }

        li {
            font-size: 24px;
            margin-bottom: 10px;
        }

        a {
            color: #1DB954;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }
    </style>
    </head>
    <body>
    <h1>Available RSS Feeds:</h1>
    <ul>
    """

    for feed in feeds:
        html += f"<li><a href='{feed['rss_url']}'>{feed['name']}</a></li>"
    
    html += """
    </ul>
    </body>
    </html>
    """

    return html

# Start the Flask app
def start_flask_app():
    flask_instance.run(debug=False, host='0.0.0.0', port=80)