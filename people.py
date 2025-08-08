import logging
import random
from typing import Any, Dict, Optional

from faker import Faker
from rich.logging import RichHandler

from chat_client import get_chat_client
from emails import EmailStore
from json_store import JsonListStore
from sms import SMSManager
from path import Path
logger = logging.getLogger(__name__)


def generate_email_from_name(name: str) -> str:
    name_parts = name.split()
    first_name = name_parts[0].lower()
    last_name = name_parts[-1].lower() if len(name_parts) > 1 else ""

    email_format = random.choice(["full_name", "initials"])
    if email_format == "full_name":
        email = f"{first_name}_{last_name}@example.org"
    else:
        initials = first_name[0] + (last_name[0] if last_name else "")
        random_number = random.randint(1, 99)
        email = f"{initials}{random_number}@example.org"

    return email


class PeopleStore(JsonListStore[Dict[str, Any]]):
    def __init__(self, file_path: str =None):
        if file_path is None:
            file_path = Path(__file__).parent / "people.json"
        super().__init__(file_path)
        self.chat_client = get_chat_client("ollama")
        self.email_manager = EmailStore()
        self.sms_manager = SMSManager()

    async def _generate_ai_response(
        self, candidate_name: str, message_type: str, message_content: str
    ) -> str:
        interested = random.random() < 0.6
        preference = "interested" if interested else "not interested"
        response = await self.chat_client.get_completion(
            [
                {
                    "role": "system",
                    "content": f"""
                        You are {candidate_name}, a job candidate.
                        Reply politely to the recruiter in 1-3 sentences.
                        You are {preference} in this opportunity.
                        """,
                },
                {
                    "role": "user",
                    "content": f"Recruiter's message:\nSubject: {message_type}\nBody: {message_content}",
                },
            ]
        )
        return response["text"]

    def _get_next_id(self) -> int:
        if not self.data:
            return 1
        return max(c.get("candidate_id", 0) for c in self.data) + 1

    def save_candidate(
        self, name: str, email: str, phone: str, status: str
    ) -> Dict[str, Any]:
        self.load()
        new_candidate = {
            "candidate_id": self._get_next_id(),
            "name": name,
            "email": email,
            "phone": phone,
            "status": status,
        }
        self.data.append(new_candidate)
        self.save()
        return new_candidate

    def generate_fake_candidates(self, n: int = 5):
        self.load()
        fake = Faker()
        for _ in range(n):
            name = fake.name()
            candidate = {
                "candidate_id": self._get_next_id(),
                "name": name,
                "email": generate_email_from_name(name),
                "phone": fake.phone_number(),
                "status": random.choice(["Available", "Not Available"]),
            }
            self.data.append(candidate)
        self.save()
        logger.info(f"Generated {n} new candidates!")

    def update_status(
        self, candidate_id: int, new_status: str
    ) -> Optional[Dict[str, Any]]:
        candidate = self.get_single("candidate_id", candidate_id)
        if candidate:
            candidate["status"] = new_status
            self.save()
            return candidate
        return None

    def update_random_statuses(self, change_probability: float = 0.3) -> int:
        updated_count = 0
        for candidate in self.get_list():
            if random.random() < change_probability:
                old_status = candidate["status"]
                candidate["status"] = (
                    "Available" if old_status == "Not Available" else "Not Available"
                )
                logger.info(
                    f"Status Update: {candidate['name']} is now {candidate['status']}"
                )
                updated_count += 1
        if updated_count > 0:
            self.save()
        return updated_count

    async def poll_and_reply_to_emails(self) -> int:
        self.load()
        replied_count = 0
        for email in self.email_manager.get_list():
            if email["response"] is None and not email["read"]:
                candidate = self.get_single("candidate_id", email["candidate_id"])
                if not candidate:
                    continue

                self.email_manager.mark_email_as_read(email["email_id"])

                if random.random() < 0.7:
                    reply = await self._generate_ai_response(
                        candidate["name"], email["subject"], email["body"]
                    )
                    self.email_manager.save_response(email["email_id"], reply)
                    replied_count += 1
                    logger.info(
                        f"Auto-reply: {candidate['name']} replied\n---\n{reply}\n---"
                    )
                else:
                    logger.info(f"{candidate['name']} ignored '{email['subject']}'")

        return replied_count

    async def poll_and_reply_to_sms(self) -> int:
        self.load()
        replied_count = 0
        for sms in self.sms_manager.get_list():
            if sms["response"] is None and not sms["read"]:
                candidate = self.get_single("candidate_id", sms["candidate_id"])
                if not candidate:
                    continue

                self.sms_manager.mark_sms_as_read(sms["sms_id"])

                if random.random() < 0.7:
                    reply = await self._generate_ai_response(
                        candidate["name"], "SMS", sms["body"]
                    )
                    self.sms_manager.save_response(sms["sms_id"], reply)
                    replied_count += 1
                    logger.info(
                        f"Auto-reply SMS: {candidate['name']} replied -> {reply}"
                    )
                else:
                    logger.info(
                        f"{candidate['name']} ignored SMS: '{sms['body'][:30]}...'"
                    )

        return replied_count


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    logger = logging.getLogger(__name__)
    manager = PeopleStore()
    manager.generate_fake_candidates(5)
