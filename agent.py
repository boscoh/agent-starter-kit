import logging
from typing import Any, Dict

import httpx
from path import Path
from pydash import py_

from candidates import CandidateStore
from jobs import JobStore
from mcp_client import MCPClient
from utils import parse_json_from_response, save_json_file
from rich.pretty import pretty_repr
logger = logging.getLogger(__name__)

debug_dir = Path(__file__).dirname() / "debug"
debug_dir.makedirs_p()

job_store = JobStore()
for job in job_store.get_list():
    job["status"] = "unfilled"
    if "candidate_ids" in job:
        job["candidate_ids"] = []
job_store.save()

candidate_store = CandidateStore()
candidate_store.clear_messages()

tool_chat_client = MCPClient("http://localhost:8080/sse", "ollama")


state = {
    "offers": {
        "candidates": [],
    },
    "jobs": job_store.get_list(),
    "replies": [],
    "candidates": candidate_store.get_list(),
}


def get_state():
    return state


def get_tools():
    return tool_chat_client.get_tools()


async def find_candidates_agent(offer):
    try:
        prompt = (
            "Give me 2 or 3 candidates who are available for the jobs "
            f"{offer['job']} that have a good match with skills.  "
            "Be really generous with the matching. "
            "Return as formatted json "
            "list only and include "
            "a skills list and a reasons list, job_id, status, candidate_id, name (of the candidate),"
            "and a score as a percentage from 0 to 100."
            "Return an empty list if no candidates are available."
            "Return as json only and nothing else."
        )
        response = await tool_chat_client.process_query(prompt)
        (debug_dir / "find_candidates.txt").write_text(response)
        proposed_candidates = parse_json_from_response(response)
        save_json_file(debug_dir / "find_candidates.json", proposed_candidates)
        return proposed_candidates
    except Exception as e:
        logger.error(f"Error parsing proposed candidates: {str(e)}")
        logger.error(response)
        return []


async def create_email_agent(proposed_candidate, job):
    try:
        prompt = (
            f"Write an short (80 words) email to ask {proposed_candidate} "
            f"if they would like a job {job}. "
            "Please return as plain text"
        )
        response = await tool_chat_client.process_query(prompt)
        (debug_dir / "create_email.txt").write_text(response)
        message = parse_json_from_response(response)
        email_data = {
            "to": proposed_candidate.get("email"),
            "from": "recruiter@company.com",
            "subject": "Job Opportunity",
            "message": message
        }
        logger.info(f"Email: {pretty_repr(email_data)}")
        save_json_file(debug_dir / "create_email.json", email_data)
        return email_data
    except Exception as e:
        logger.error(f"Error parsing email data: {str(e)}")
        return {}


async def classify_email_agent(email):
    try:
        prompt = (
            "Classify the following email in terms of: 'interested' or 'rejected'"
            f"{email['response']['text']}"
            "Return with a single classification."
        )
        classification = await tool_chat_client.process_query(prompt)
        (debug_dir / "classify_email.txt").write_text(classification)
        return classification
    except Exception as e:
        logger.error(f"Error classifying email: {str(e)}")
        return ""


async def check_jobs():
    global state

    logger.info("Start check jobs")

    offers = state["offers"]
    offers["candidates"] = []
    offers["job"] = py_.sample(state["jobs"])
    logger.info("Find candidates agent...")
    proposed_candidates = await find_candidates_agent(offers)
    logger.info("Find candidates agent finished.")

    for proposed_candidate in proposed_candidates:
        try:
            offers["candidates"].insert(0, proposed_candidate)

            logger.info("Create emails agent...")
            email_text = await create_email_agent(proposed_candidate, offers["job"])
            logger.info("Create emails finished.")

            proposed_candidate["sent_email"] = email_text

            name = proposed_candidate["name"]
            candidate = py_.find(state["candidates"], lambda c: c["name"] == name)
            if not candidate:
                continue
            candidate_store.update_candidate_status(
                candidate["candidate_id"], "requested", offers["job"]["job_id"]
            )
            candidate_store.add_message(
                candidate["candidate_id"], proposed_candidate["sent_email"]
            )
            state["candidates"] = candidate_store.get_list()
            await send_email(candidate, proposed_candidate["sent_email"])
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")

    logger.info("Finished sending emails emails")


async def check_candidates_replies():
    global state

    logger.info("Checking emails for candidate")
    for email in await read_emails():
        email_id = email["email_id"]
        processed_email = py_.find(
            state["replies"], lambda r: r["email"]["email_id"] == email_id
        )
        if processed_email:
            continue
        if not py_.get_list(email, "response.text"):
            continue
        candidate = py_.find(
            state["candidates"],
            lambda c: c["candidate_id"] == email["candidate_id"],
        )
        try:
            logger.info(f"Classifyng response from candidate {candidate['name']}")
            logger.info(f"Email {email['email_id']}: {email['response']['text']}")
            classification = await classify_email_agent(email)
            logger.info(f"Classification: {classification}")
            state["candidates"] = candidate_store.get_list()
            state["replies"].insert(
                0,
                {
                    "candidate": candidate,
                    "email": email,
                    "classification": classification,
                    "jobId": candidate["job_id"],
                },
            )
            if "interested" in classification.lower():
                job_store.update_job_availability(
                    candidate["job_id"], True, candidate["candidate_id"]
                )
            else:
                job_store.update_job_availability(
                    candidate["job_id"], False, candidate["candidate_id"]
                )
            state["jobs"] = job_store.get_list()

            candidate_store.add_message(candidate["candidate_id"], email)
        except Exception as e:
            logger.error(
                f"Error classifying email for candidate {candidate['name']} ({email['id']}): {e}"
            )
    logger.info("Finished checking emails")


async def send_email(candidate: Dict[str, Any], email_data: Dict[str, str]) -> bool:
    try:
        url = f"http://127.0.0.1:8000/send-email/{candidate['candidate_id']}"
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=email_data, headers=headers)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False


async def read_emails():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000/emails")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error reading emails: {str(e)}")
        return []
