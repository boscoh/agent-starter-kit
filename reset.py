from path import Path
from people import PeopleStore
from candidates import CandidateStore
from jobs import JobStore
import asyncio
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

f = Path("people.json")
if f.exists():
    f.unlink()
people_store = PeopleStore()
people_store.generate_fake_candidates(5)
people_store.save()

candidate_store = CandidateStore()
candidate_store.generate_fake_candidates()
candidate_store.save()

job_store = JobStore()
asyncio.run(job_store.async_generate_fake_jobs(5))
job_store.save()
