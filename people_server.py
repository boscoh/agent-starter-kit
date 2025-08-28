import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from path import Path
from rich.logging import RichHandler

from emails import EmailStore
from people import PeopleStore

logger = logging.getLogger(__name__)

people_manager = PeopleStore()
email_manager = EmailStore()


async def poll_email_reply_loop(stop_event: asyncio.Event):
    logger.info("Initialise poll_email_reply_loop")
    while not stop_event.is_set():
        try:
            replied_count = await people_manager.poll_and_reply_to_emails()
            if replied_count > 0:
                logger.info(
                    f"Auto-poll: {replied_count} candidate(s) replied to emails."
                )
            else:
                logger.debug("Auto-poll: No new email replies.")
        except Exception as e:
            logger.error(f"Error in email reply polling loop: {str(e)}", exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass


async def status_update_loop(stop_event: asyncio.Event):
    logger.info("Initialise status_update_loop")
    while not stop_event.is_set():
        try:
            updated_count = people_manager.update_random_statuses()
            if updated_count > 0:
                logger.info(
                    f"Status update: Updated {updated_count} candidate(s) status."
                )
            else:
                logger.debug("Status update: No status updates needed.")
        except Exception as e:
            logger.error(f"Error in status update loop: {str(e)}", exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    stop_event = asyncio.Event()

    # Start background tasks
    tasks = [
        asyncio.create_task(poll_email_reply_loop(stop_event)),
        asyncio.create_task(status_update_loop(stop_event)),
    ]

    logger.info("Background tasks started")

    try:
        yield
    finally:
        logger.info("Shutting down application...")
        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Background tasks stopped")


app = FastAPI(
    title="Candidate Email Management API", version="1.5.0", lifespan=lifespan
)


@app.get("/")
async def read_root():
    """
    Serve the main HTML interface.

    Returns:
        FileResponse: The people.html file
    """
    index_path = os.path.join(os.path.dirname(__file__), "people.html")
    return FileResponse(index_path)


@app.post("/generate-candidates/{count}")
async def generate_candidates(count: int):
    """
    Generate fake candidate data for testing.

    Args:
        count (int): Number of fake candidates to generate

    Example:
        curl -X POST "http://localhost:8000/generate-candidates/5"

    Returns:
        dict: Message and list of generated candidates
    """
    new_candidates = people_manager.generate_fake_people(count)
    return {
        "message": f"{count} fake candidates generated successfully",
        "candidates": new_candidates,
    }


@app.post("/create-candidate")
async def create_candidate(request: Request):
    """
    Create a new candidate.

    Request Body:
        - name (str): Candidate's full name
        - email (str): Candidate's email
        - phone (str): Candidate's phone number
        - status (str, optional): Initial status (default: "Available")

    Example:
        curl -X POST "http://localhost:8000/create-candidate" \
          -H "Content-Type: application/json" \
          -d '{"name": "John Doe", "email": "john@example.com", "phone": "+1234567890"}'

    Returns:
        dict: Success message and created candidate data
    """
    data = await request.json()
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    status = data.get("status", "Available")

    if not name or not email or not phone:
        raise HTTPException(
            status_code=400, detail="Name, email, and phone are required"
        )

    candidate = people_manager.save_candidate(name, email, phone, status)

    return {"message": "Candidate created successfully", "candidate": candidate}


@app.get("/candidates/")
async def list_candidates(
    status: Optional[str] = Query(
        None, description="Filter by status, e.g., Available"
    ),
):
    """
    List all candidates, optionally filtered by status.

    Args:
        status (str, optional): Filter candidates by status

    Examples:
        # Get all candidates
        curl -X GET "http://localhost:8000/candidates/"

        # Get available candidates
        curl -X GET "http://localhost:8000/candidates/?status=Available"

    Returns:
        list: List of candidate dictionaries
    """
    logger.info(f"Listing candidates status={status}")
    try:
        if status is None:
            candidates = people_manager.get_list()
        else:
            candidates = people_manager.get_list("status", status)
        logger.debug(f"Found {len(candidates)} candidates")
        return candidates
    except Exception as e:
        logger.error(f"Error listing candidates: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send-email")
async def send_email(request: Request):
    """
    Send an email to a candidate.

    Request Body:
        - to (str): Recipient email (candidate's email)
        - from (str): Sender email (recruiter's email)
        - subject (str): Email subject
        - message (str): Email body

    Example:
        curl -X POST "http://localhost:8000/send-email" \
          -H "Content-Type: application/json" \
          -d '{"to": "candidate@example.com", "from": "recruiter@company.com", "subject": "Interview", "message": "Hello!"}'

    Returns:
        dict: Success message and email details

    Raises:
        HTTPException: 404 if candidate not found, 400 for missing fields
    """
    data = await request.json()
    candidate_email = data.get("to")
    recruiter_email = data.get("from")
    subject = data.get("subject")
    message = data.get("message")

    if not candidate_email or not recruiter_email or not subject or not message:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: to, from, subject, message",
        )

    candidate = people_manager.get_single("email", candidate_email)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate Not found")

    candidate_id = candidate.get("candidate_id")
    logger.info(f"Candidate {candidate_id} found for email {candidate_email}")

    email_entry = email_manager.send_email_by_candidate_id(
        candidate_id=candidate_id,
        to_email=candidate_email,
        from_email=recruiter_email,
        subject=subject,
        message=message,
    )

    return {"message": f"Email sent to {candidate['name']}", "email": email_entry}


@app.get("/emails")
async def list_emails(
    candidate_id: int | None = Query(None, description="Filter by candidate_id"),
):
    """
    List all emails, optionally filtered by candidate.

    Args:
        candidate_id (int, optional): Filter emails by candidate ID

    Examples:
        # Get all emails
        curl -X GET "http://localhost:8000/emails"

        # Get emails for specific candidate
        curl -X GET "http://localhost:8000/emails?candidate_id=1"

    Returns:
        list: List of email dictionaries
    """
    logger.info("Listing emails")
    if candidate_id:
        result = email_manager.get_list("candidate_id", candidate_id)
    else:
        result = email_manager.get_list()
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True  # Disable access logs

    logger.info("Starting People Server...")
    uvicorn.run(
        f"{Path(__file__).stem}:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_config=None,  # Disable uvicorn's default logging config
        access_log=False,  # Disable uvicorn access logs
    )
