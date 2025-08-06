import logging
import os
from typing import Any, Dict, List, Optional

from json_store import JsonListStore
from utils import _current_timestamp

# Configure logger
logger = logging.getLogger(__name__)


class SMSManager(JsonListStore[Dict[str, Any]]):
    def __init__(self, filename: str = "sms.json"):
        super().__init__(filename)
        if not os.path.exists(self.json_file):
            logger.info(f"Creating new SMS store at {self.json_file}")
            self.save()
        else:
            logger.debug(f"Loaded existing SMS store from {self.json_file}")

    def _get_next_sms_id(self) -> int:
        return max((sms["sms_id"] for sms in self.get_list()), default=0) + 1

    def send_sms(
        self,
        candidate_id: int,
        candidate_phone: str,
        recruiter_phone: str,
        message: str,
    ) -> Dict[str, Any]:
        logger.info(f"Sending SMS to candidate {candidate_id} at {candidate_phone}")
        sms_entry = {
            "sms_id": self._get_next_sms_id(),
            "candidate_id": candidate_id,
            "from": recruiter_phone,
            "to": candidate_phone,
            "body": message,
            "timestamp": _current_timestamp(),
            "response": None,
            "read": False,
        }
        self.data.append(sms_entry)
        self.save()
        logger.info(f"SMS sent to {candidate_phone} (ID: {sms_entry['sms_id']})")
        return sms_entry

    def mark_sms_as_read(self, sms_id: int) -> Optional[Dict[str, Any]]:
        sms = self.get_single("sms_id", sms_id)
        if sms:
            if not sms["read"]:
                sms["read"] = True
                self.save()
                logger.info(f"Marked SMS {sms_id} as read")
            else:
                logger.debug(f"SMS {sms_id} was already marked as read")
            return sms
        logger.warning(f"Attempted to mark non-existent SMS {sms_id} as read")
        return None

    def save_response(self, sms_id: int, reply_text: str) -> Optional[Dict[str, Any]]:
        sms = self.get_single("sms_id", sms_id)
        if sms:
            logger.info(f"Saving response to SMS {sms_id}")
            sms["response"] = {
                "text": reply_text,
                "timestamp": _current_timestamp(),
            }
            sms["read"] = True
            self.save()
            logger.debug(f"Response saved for SMS {sms_id}")
            return sms
        logger.warning(f"Attempted to save response to non-existent SMS {sms_id}")
        return None

    def get_sms_by_recruiter(self, recruiter_phone: str) -> List[Dict[str, Any]]:
        return self.get_list("from", recruiter_phone)
