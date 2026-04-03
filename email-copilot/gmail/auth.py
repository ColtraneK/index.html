"""Gmail OAuth2 authentication with encrypted token storage."""

import json
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from security.encryption import decrypt_from_file, encrypt_to_file

logger = logging.getLogger(__name__)


def _build_client_config(client_id: str, client_secret: str) -> dict:
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def get_credentials(
    client_id: str,
    client_secret: str,
    scopes: list[str],
    token_path: Path,
    encryption_passphrase: str,
) -> Credentials:
    """Get valid Gmail credentials, prompting OAuth flow if needed.

    Tokens are stored encrypted on disk using the provided passphrase.
    """
    creds = None

    if token_path.exists():
        try:
            token_json = decrypt_from_file(token_path, encryption_passphrase)
            creds = Credentials.from_authorized_user_info(json.loads(token_json), scopes)
            logger.info("Loaded existing credentials from encrypted token file.")
        except Exception as e:
            logger.warning("Failed to load stored token: %s. Re-authenticating.", e)
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Refreshed expired credentials.")
            _save_credentials(creds, token_path, encryption_passphrase)
        except Exception as e:
            logger.warning("Failed to refresh token: %s. Re-authenticating.", e)
            creds = None

    if not creds or not creds.valid:
        client_config = _build_client_config(client_id, client_secret)
        flow = InstalledAppFlow.from_client_config(client_config, scopes)
        creds = flow.run_local_server(port=8080, open_browser=True)
        logger.info("Completed OAuth2 flow. Saving encrypted token.")
        _save_credentials(creds, token_path, encryption_passphrase)

    return creds


def _save_credentials(creds: Credentials, token_path: Path, passphrase: str) -> None:
    token_data = json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes and list(creds.scopes),
    })
    encrypt_to_file(token_data, passphrase, token_path)
