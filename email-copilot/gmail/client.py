"""Gmail API client for reading emails and sending replies."""

import base64
import logging
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from gmail.auth import get_credentials
from gmail.parser import parse_message

logger = logging.getLogger(__name__)


class GmailClient:
    """Wrapper around Gmail API for email operations."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: list[str],
        token_path,
        encryption_passphrase: str,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = scopes
        self._token_path = token_path
        self._encryption_passphrase = encryption_passphrase
        self._service = None

    def _get_service(self):
        if self._service is None:
            creds = get_credentials(
                self._client_id,
                self._client_secret,
                self._scopes,
                self._token_path,
                self._encryption_passphrase,
            )
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch_new_emails(self, max_results: int = 20, since_id: str | None = None) -> list[dict]:
        """Fetch recent unread emails from inbox.

        Returns list of parsed email dicts.
        """
        service = self._get_service()
        query = "is:unread is:inbox"

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
        except Exception as e:
            logger.error("Failed to list messages: %s", e)
            return []

        messages = results.get("messages", [])
        if not messages:
            return []

        parsed = []
        for msg_stub in messages:
            if since_id and msg_stub["id"] == since_id:
                break
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_stub["id"], format="full")
                    .execute()
                )
                parsed.append(parse_message(msg))
            except Exception as e:
                logger.error("Failed to fetch message %s: %s", msg_stub["id"], e)

        return parsed

    def send_reply(self, thread_id: str, to_address: str, subject: str, body: str) -> bool:
        """Send a reply email in the given thread."""
        service = self._get_service()

        message = MIMEText(body)
        message["to"] = to_address
        message["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            service.users().messages().send(
                userId="me",
                body={"raw": raw, "threadId": thread_id},
            ).execute()
            logger.info("Sent reply to %s in thread %s", to_address, thread_id)
            return True
        except Exception as e:
            logger.error("Failed to send reply: %s", e)
            return False

    def get_user_email(self) -> str:
        """Get the authenticated user's email address."""
        service = self._get_service()
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress", "")
