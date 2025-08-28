import logging
from typing import Any, Dict, List, Optional

from path import Path

from json_store import JsonListStore
from utils import _current_timestamp

logger = logging.getLogger(__name__)


class EmailStore(JsonListStore[Dict[str, Any]]):
    def __init__(self, filename: str = None):
        if filename is None:
            filename = Path(__file__).parent / "emails.json"
        super().__init__(filename)

    def _get_next_email_id(self) -> int:
        if not self.data:
            return 1
        return max(c.get("email_id", 0) for c in self.data) + 1

    def send_email_by_candidate_id(
        self,
        candidate_id: int,
        to_email: str,
        from_email: str,
        subject: str,
        message: str,
    ) -> Dict[str, Any]:
        logger.info(f"Sending email to candidate {candidate_id} at {to_email}")
        email_entry = {
            "email_id": self._get_next_email_id(),
            "candidate_id": candidate_id,
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "body": message,
            "timestamp": _current_timestamp(),
            "response": None,
            "read": False,
        }
        self.data.append(email_entry)
        self.save()
        logger.info(f"Email sent to {to_email} (ID: {email_entry['email_id']})")
        return email_entry

    def mark_email_as_read(self, email_id: int) -> Optional[Dict[str, Any]]:
        email = self.get_single("email_id", email_id)
        if email:
            if not email["read"]:
                email["read"] = True
                self.save()
                logger.info(f"Marked email {email_id} as read")
            else:
                logger.debug(f"Email {email_id} was already marked as read")
            return email
        logger.warning(f"Attempted to mark non-existent email {email_id} as read")
        return None

    def save_response(self, email_id: int, reply_text: str) -> Optional[Dict[str, Any]]:
        email = self.get_single("email_id", email_id)
        if email:
            logger.info(f"Saving response to email {email_id}")
            email["response"] = {
                "text": reply_text,
                "timestamp": _current_timestamp(),
            }
            email["read"] = True
            self.save()
            logger.debug(f"Response saved for email {email_id}")
            return email
        logger.warning(f"Attempted to save response to non-existent email {email_id}")
        return None

    def get_emails_by_from(self, email: str) -> List[Dict[str, Any]]:
        return self.get_list("from", email)
