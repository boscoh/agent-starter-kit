import asyncio
import logging

from rich.logging import RichHandler

from candidates import CandidateStore
from jobs import JobStore
from people import PeopleStore

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

people_store = PeopleStore()
people_store.clear()
people_store.generate_fake_candidates(5)
people_store.save()

candidate_store = CandidateStore()
candidate_store.clear()
candidate_store.generate_fake_candidates()
candidate_store.save()

job_store = JobStore()
job_store.clear()
asyncio.run(job_store.async_generate_fake_jobs(5))
job_store.save()
