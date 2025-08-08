import asyncio
import logging
import os
import random
import string
from typing import Any, Dict, Optional, Set
from path import Path
from rich.logging import RichHandler
from rich.pretty import pretty_repr

from json_store import JsonListStore
from utils import load_json_file, parse_json_from_response


class JobStore(JsonListStore[Dict[str, Any]]):
    def __init__(self, json_file: str = None):
        if json_file is None:
            json_file = Path(__file__).parent / "jobs.json"
        super().__init__(json_file)

    def update_job_availability(
        self, job_id: str, filled: bool, candidate_id: Optional[str] = None
    ) -> bool:
        self.logger.info(
            f"Updating job {job_id} availability to {'filled' if filled else 'unfilled'}"
        )
        job = self.get_single("job_id", job_id)

        if not job:
            self.logger.warning(f"Job {job_id} not found for update")
            return False

        old_status = job.get("status", "unknown")
        job["status"] = "filled" if filled else "unfilled"

        if not filled:
            removed_candidates = len(job.get("candidate_ids", []))
            job["candidate_ids"] = []
            self.logger.info(
                f"Job {job_id} marked as unfilled. Removed {removed_candidates} candidates"
            )
        else:
            if "candidate_ids" not in job:
                job["candidate_ids"] = []
            if candidate_id and candidate_id not in job["candidate_ids"]:
                job["candidate_ids"].append(candidate_id)
                self.logger.info(f"Added candidate {candidate_id} to job {job_id}")

        self.save()
        self.logger.info(
            f"Updated job {job_id} status from {old_status} to {job['status']}"
        )
        return True

    async def async_generate_fake_jobs(self, n: int) -> None:
        self.data = await generate_fake_jobs(n, "candidates.json")
        self.save()


async def generate_fake_jobs(
    n: int, candidates_json: str = "candidates.json", chat_client_type: str = "ollama"
) -> list[dict[str, Any]]:
    logger.info(f"Generating {n} fake jobs using {candidates_json}")

    try:
        from chat_client import get_chat_client

        chat_client = get_chat_client(chat_client_type)
        logger.info(f"Successfully initialized chat client: {chat_client_type}")
    except Exception as e:
        logger.error(f"Failed to initialize chat client: {e}")
        return []

    candidate_skills: Set[str] = set()
    if os.path.exists(candidates_json):
        try:
            candidates = load_json_file(candidates_json)
            for candidate in candidates:
                if "skills" in candidate and isinstance(candidate["skills"], list):
                    candidate_skills.update(s.lower() for s in candidate["skills"])
            logger.info(f"Loaded {len(candidate_skills)} unique skills from candidates")
        except Exception as e:
            logger.error(f"Failed to load candidate skills: {e}", exc_info=True)
    else:
        logger.warning(f"Candidates file {candidates_json} not found")

    async def get_title():
        skills_sample = "\n- ".join(
            random.sample(list(candidate_skills), min(5, len(candidate_skills)))
        )
        prompt = (
            "Generate a realistic job title for a tech company. "
            "The title should be related to these skills:\n"
            f"- {skills_sample}\n\n"
            "Return only the job title of four words or less, nothing else."
        )
        try:
            messages = [{"role": "user", "content": prompt}]
            logger.info("Generating title...")
            resp = await chat_client.get_completion(messages)
            title = resp["text"].strip()
            logger.info(f"Generated title: {title}")
            return title
        except Exception as e:
            logger.warning(
                f"Failed to get title from chat_client: {e}. Using random title."
            )
            return (
                random.choice(list(candidate_skills))
                if candidate_skills
                else "Software Engineer"
            )

    async def get_description(title):
        skills_sample = "\n- ".join(
            random.sample(list(candidate_skills), min(5, len(candidate_skills)))
        )
        prompt = (
            f"Write a short, realistic job description for the position titled: '{title}'.\n"
            "The job should require skills from this list (but don't list them explicitly):\n"
            f"- {skills_sample}\n\n"
            "Focus on responsibilities and qualifications. Keep it concise (2-3 sentences)."
            "Return only the description, nothing else."
        )
        try:
            messages = [{"role": "user", "content": prompt}]
            logger.info(f"Generating description for title: {title}")
            resp = await chat_client.get_completion(messages)
            description = resp["text"].strip()
            logger.info(f"Generated description for {title}")
            return description
        except Exception as e:
            logger.warning(
                f"Failed to get description from chat_client: {e}. Using static description."
            )
            return f"Description for {title}"

    async def get_skills(title, description):
        if not candidate_skills:
            default_skills = ["Python", "JavaScript", "Problem Solving"]
            logger.info("No candidate skills found, using default skills")
            return default_skills

        try:
            logger.info(f"Generating skills for: {title}")
            prompt = (
                "Based on this job title and description:\n\n"
                f"Title: {title}\n"
                f"Description: {description}\n\n"
                "Select 3-5 skills from this list that are most relevant. "
                "Return as a JSON array of strings.\n"
                f"Available skills: {', '.join(sorted(candidate_skills))}\n\n"
                "Return as JSON only and nothing else."
            )
            messages = [{"role": "user", "content": prompt}]
            resp = await chat_client.get_completion(messages)
            parsed = parse_json_from_response(resp["text"])
            logger.info(f"Generated skills for {title}: {pretty_repr(parsed)}")
            return parsed
        except Exception as e:
            logger.warning(
                f"Failed to get skills from chat_client: {e}. Using random skills."
            )
            num_skills = random.randint(3, min(5, len(candidate_skills)))
            return random.sample(list(candidate_skills), num_skills)

    logger.info(f"Starting to generate {n} job listings")
    tasks = []
    for _ in range(n):
        job_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        filled = False
        employee_id = (
            "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if filled
            else None
        )
        tasks.append((job_id, filled, employee_id))

    logger.info("Generating job titles...")
    titles = await asyncio.gather(*[get_title() for _ in range(n)])
    logger.info(f"Generated {len(titles)} titles")

    logger.info("Generating job descriptions...")
    descriptions = await asyncio.gather(*[get_description(title) for title in titles])
    logger.info(f"Generated {len(descriptions)} descriptions")

    logger.info("Generating required skills...")
    skills = await asyncio.gather(
        *[get_skills(title, desc) for title, desc in zip(titles, descriptions)]
    )
    logger.info(f"Generated skills for {len(skills)} jobs")

    jobs = []
    for (job_id, filled, employee_id), title, description, job_skills in zip(
        tasks, titles, descriptions, skills
    ):
        job = {
            "job_id": job_id,
            "title": title,
            "description": description,
            "skills": job_skills,
            "status": "unfilled",
            "candidate_ids": [],
        }
        jobs.append(job)
        logger.info(f"Created job: {job_id} - {title}")

    logger.info(f"Successfully generated {len(jobs)} jobs")
    return jobs


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    logger = logging.getLogger(__name__)
    job_store = JobStore()

    async def main():
        await job_store.async_generate_fake_jobs(8)

    asyncio.run(main())
