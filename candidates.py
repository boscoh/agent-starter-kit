import logging
import random
from typing import Literal, Optional

from rich.logging import RichHandler
from rich.pretty import pretty_repr

from json_store import JsonListStore
from utils import load_json_file

logger = logging.getLogger(__name__)

# Define the possible status values
CandidateStatus = Literal["available", "requested", "unavailable", "assigned"]


class CandidateStore(JsonListStore[dict]):
    def __init__(self, json_file: str = "people.json"):
        super().__init__(json_file)
        self._normalize_candidates()

    def _normalize_candidates(self):
        for candidate in self.data:
            if "available" in candidate:
                if "status" not in candidate:
                    candidate["status"] = (
                        "available" if candidate.pop("available") else "unavailable"
                    )
                else:
                    candidate.pop("available")
            elif "status" not in candidate:
                candidate["status"] = "available"

    def update_candidate_status(
        self, candidate_id: str, status: CandidateStatus, job_id: Optional[str] = None
    ) -> bool:
        candidate = self.get_single("candidate_id", candidate_id)
        if candidate:
            candidate["status"] = status
            candidate["job_id"] = job_id
            self.save()
            return True
        return False

    def add_message(self, candidate_id: str, message: any) -> bool:
        candidate = self.get_single("candidate_id", candidate_id)
        if candidate:
            if "messages" not in candidate:
                candidate["messages"] = []
            candidate["messages"].append(message)
            self.save()
            return True
        return False

    def clear_messages(self) -> None:
        for candidate in self.get_list():
            candidate["status"] = "available"
            candidate["messages"] = []
        self.save()

    async def async_generate_fake_candidates(self, n: int):
        self.data = []
        real_candidates = load_json_file("people.json")
        for i in range(n):
            candidate = random.choice(real_candidates)
            candidate = {
                "candidate_id": i + 1,
                "name": candidate["name"],
                "email": f"user{i}@example.com",
                "phone": f"+1{random.randint(2000000000, 9999999999)}",
                "status": "available",
                "skills": candidate.get("skills", []),
                "job_id": None,
            }
            self.data.append(candidate)
        self.save()
        return self.data


async def main():
    store = CandidateStore()
    candidates = store.get_list()
    logger.info(f"Loaded {len(candidates)} candidates")
    logger.debug(pretty_repr(candidates))
    await store.async_generate_fake_candidates(5)


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    logger = logging.getLogger(__name__)

    asyncio.run(main())
