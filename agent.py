import logging
import re
from typing import Any, Dict

import httpx
from path import Path
from pydash import py_

from candidates import CandidateStore
from jobs import JobStore
from mcp_client import MCPClient
from utils import parse_json_from_response, save_json_file

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
for candidate in candidate_store.get_list():
    candidate["status"] = "available"
    candidate["messages"] = []
candidate_store.save()

mcp_chat_client = MCPClient("http://localhost:8080/sse", "ollama")


state = {
    "candidates": candidate_store.get_list(),
    "jobs": job_store.get_list(),
    "currentJob": None,
    "currentMatches": [],
    "matches": [],
    "replies": [],
}


def get_state():
    return state


def get_tools():
    return mcp_chat_client.get_tools()


async def find_candidates_agent(job):
    logger.info("find_candidates_agent: start")
    result = []
    response = ""
    try:
        prompt = f"""
            Give me 2 or 3 candidates who are available for the jobs 
            {job} that have a good match with skills.  
            Be really generous with the matching. 
            Return as formatted json list in the format:
             [
                {{
                    "candidate_id": <candidate_id>,
                    "name": <candidate_name>,
                    "score": <score_as_percentage>,
                    "job_id": <job_id>,
                    "skills": [
                        "<candidate skill 1>",
                        "<candidate skill 2>",
                    ],
                    "reasons": [
                        "<reason 1>",
                        "<reason 2>",
                    ]
                }}
            ]
            Give reasons as short sentences.
            Return an empty list if no candidates are available.
            Return as JSON only, and nothing else.
            """
        response = await mcp_chat_client.process_query(prompt)
        (debug_dir / "find_candidates.txt").write_text(response)
        matches = parse_json_from_response(response)
        if isinstance(matches, list):
            save_json_file(debug_dir / "find_candidates.json", matches)
            result = matches
        else:
            logger.error(f"Error getting proposed candidates: {matches}")
    except Exception as e:
        logger.error(f"Error getting proposed candidates: {e}", exc_info=True)
        logger.error(response)
    logger.info(f"find_candidates_agent: finish - found {len(result)} candidates")
    return result


async def create_email_agent(candidate, job):
    logger.info("create_email_agent: start")
    response = ""
    try:
        prompt = (
            f"Write an short (80 words) message to ask {candidate['name']} "
            f"if they would like a job {job}. "
            "Don't use tools. Do not use JSON."
            "Return the text message directly."
        )
        response = await mcp_chat_client.process_query(prompt)
        (debug_dir / "create_email.txt").write_text(response)
        response = parse_json_from_response(response)
        email_data = {
            "to": candidate.get("email"),
            "from": "recruiter@company.com",
            "subject": "Job Opportunity",
            "message": str(response),
        }
        save_json_file(debug_dir / "create_email.json", email_data)
    except Exception as e:
        logger.error(f"Error parsing email data: {e}", exc_info=True)
        email_data = {}
    logger.info(f"create_email_agent: finish\n---\n{str(response)}\n---")
    return email_data


def get_word(text):
    words = re.findall(r"\b\w+\b|[^\w\s]", text)
    return words[0].lower() if words else ""


async def classify_email_agent(message):
    logger.info("classify_email_agent: start")
    classification = "not clear"
    try:
        prompt = (
            "Classify the following email in terms of: 'interested' or 'rejected'"
            f"'{message}'"
            "Please return with a single word, and nothing else."
        )
        response = await mcp_chat_client.process_query(prompt)
        response = parse_json_from_response(response)
        response = str(response)
        (debug_dir / "classify_email.txt").write_text(response)
        if len(response.split()) == 1:
            classification = get_word(response)
    except Exception as e:
        logger.error(f"Error classifying email: {e}", exc_info=True)
    logger.info(f"---\n{message}\n---")
    logger.info(f"classify_email_agent: finish `{classification}`")
    return classification


async def check_jobs():
    global state

    logger.info("check_jobs: start")

    job = py_.sample(state["jobs"])
    state["currentMatches"] = []
    state["currentJob"] = job
    n_sent = 0

    for match in await find_candidates_agent(job):
        try:
            candidate = py_.find(
                state["candidates"], lambda c: c["name"] == match.get("name")
            )
            if not candidate:
                continue
            state["currentMatches"].insert(0, match)
            state["matches"].insert(0, match)

            email_data = await create_email_agent(candidate, job)
            match["sent_email"] = email_data

            candidate_store.add_message(candidate["candidate_id"], email_data)
            candidate_store.update_candidate_status(
                candidate["candidate_id"], "requested", job["job_id"]
            )
            await send_email(candidate, email_data)

            state["candidates"] = candidate_store.get_list()
            n_sent += 1
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)

    logger.info(f"check_jobs: finish - sent emails to {n_sent} candidates")


async def check_candidates_replies():
    global state

    logger.info("check_candidates_replies: start")
    for email in await read_emails():
        email_id = email["email_id"]
        processed_email = py_.find(
            state["replies"], lambda r: r["email"]["email_id"] == email_id
        )
        if processed_email:
            continue
        if not py_.get(email, "response.text"):
            continue
        candidate_id = email["candidate_id"]
        candidate = py_.find(
            state["candidates"],
            lambda c: c["candidate_id"] == candidate_id,
        )
        job_id = candidate["job_id"]
        try:
            classification = await classify_email_agent(email["response"]["text"])
            state["replies"].insert(
                0,
                {
                    "candidate": candidate,
                    "email": email,
                    "classification": classification,
                    "jobId": job_id,
                },
            )

            available = "interested" in classification.lower()
            job_store.update_job_availability(job_id, available, candidate_id)
            state["jobs"] = job_store.get_list()

            candidate_store.add_message(candidate_id, email)
            state["candidates"] = candidate_store.get_list()
        except Exception as e:
            logger.error(f"Error classifying email: {e}", exc_info=True)
    logger.info("check_candidates_replies: finish")


async def send_email(candidate: Dict[str, Any], email_data: Dict[str, str]) -> bool:
    try:
        url = f"http://127.0.0.1:8000/send-email/{candidate['candidate_id']}"
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=email_data, headers=headers)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        return False


async def read_emails():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000/emails")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error reading emails: {e}", exc_info=True)
        return []
