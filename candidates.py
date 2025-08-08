import logging
import random
from typing import Literal, Optional

from path import Path
from rich.logging import RichHandler
from rich.pretty import pretty_repr

from json_store import JsonListStore
from utils import load_json_file

logger = logging.getLogger(__name__)

CandidateStatus = Literal["available", "requested", "unavailable", "assigned"]


class CandidateStore(JsonListStore[dict]):
    def __init__(self, json_file: str = None):
        if json_file is None:
            json_file = Path(__file__).parent / "candidates.json"
        super().__init__(json_file)

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

    def generate_fake_candidates(self):
        self.data = []
        people = load_json_file("people.json")
        for person in people:
            skills = random.sample(
                [
                    "Python",
                    "JavaScript",
                    "SQL",
                    "AWS",
                    "Docker",
                    "Kubernetes",
                    "React",
                    "Django",
                    "Flask",
                    "Machine Learning",
                ],
                k=random.randint(3, 6),
            )
            candidate = {
                "candidate_id": person["candidate_id"],
                "name": person["name"],
                "email": person["email"],
                "phone": person["phone"],
                "status": "available",
                "skills": skills,
                "job_id": None,
            }
            self.data.append(candidate)
        self.save()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    store = CandidateStore()
    store.generate_fake_candidates()
    candidates = store.get_list()
    logger.info(f"Loaded {len(candidates)} candidates")
    logger.debug(pretty_repr(candidates))
