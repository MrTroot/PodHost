# spotify_auth.py
import json
from librespot.core import Session

class ZotifyAuth:
    @classmethod
    def login(cls, username, password, credentials_file):
        if not credentials_file:
            raise ValueError("credentials_file must be provided")

        try:
            conf = Session.Configuration.Builder().set_store_credentials(False).build()
            Session.Builder(conf).stored_file(credentials_file).create()
            return
        except RuntimeError:
            pass

        try:
            if not username or not password:
                raise ValueError("username and password must be provided")

            conf = Session.Configuration.Builder().set_stored_credential_file(credentials_file).build()
            Session.Builder(conf).user_pass(username, password).create()
            return
        except RuntimeError:
            raise ValueError("Invalid username or password")
