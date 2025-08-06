import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from rich.logging import RichHandler
import uvicorn

from emails import EmailStore
from people import PeopleStore
from sms import SMSManager


logger = logging.getLogger(__name__)

people_manager = PeopleStore()
email_manager = EmailStore()
sms_manager = SMSManager()


async def poll_email_reply_loop(stop_event: asyncio.Event):
    logger.info("Starting email reply polling loop")
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


async def poll_sms_reply_loop(stop_event: asyncio.Event):
    logger.info("Starting SMS reply polling loop")
    while not stop_event.is_set():
        try:
            replied_count = await people_manager.poll_and_reply_to_sms()
            if replied_count > 0:
                logger.info(f"Auto-poll: {replied_count} candidate(s) replied to SMS.")
            else:
                logger.debug("Auto-poll: No new SMS replies.")
        except Exception as e:
            logger.error(f"Error in SMS reply polling loop: {str(e)}", exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass


async def status_update_loop(stop_event: asyncio.Event):
    logger.info("Starting status update loop")
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
            await asyncio.wait_for(stop_event.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    stop_event = asyncio.Event()

    # Start background tasks
    tasks = [
        asyncio.create_task(poll_email_reply_loop(stop_event)),
        asyncio.create_task(poll_sms_reply_loop(stop_event)),
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
    new_candidates = people_manager.generate_fake_candidates(count)
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
    logger.info(f"Listing candidates with status filter: {status}")
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


@app.put("/update-status/{candidate_id}")
async def update_status(
    candidate_id: int,
    status: str = Query(..., description="New status, e.g., Available"),
):
    """
    Update a candidate's status.

    Args:
        candidate_id (int): ID of the candidate to update
        status (str): New status value

    Example:
        curl -X PUT "http://localhost:8000/update-status/1?status=Interviewing"

    Returns:
        dict: Success message and updated candidate data

    Raises:
        HTTPException: 404 if candidate not found
    """
    updated_candidate = people_manager.update_status(candidate_id, status)

    if not updated_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "message": f"Candidate {updated_candidate['name']}'s status updated to {status}",
        "candidate": updated_candidate,
    }


@app.post("/send-email/{candidate_id}")
async def send_email(candidate_id: int, request: Request):
    """
    Send an email to a candidate.

    Args:
        candidate_id (int): ID of the candidate to email

    Request Body:
        - to (str): Recipient email (candidate's email)
        - from (str): Sender email (recruiter's email)
        - subject (str): Email subject
        - message (str): Email body

    Example:
        curl -X POST "http://localhost:8000/send-email/1" \
          -H "Content-Type: application/json" \
          -d '{"to": "candidate@example.com", "from": "recruiter@company.com", "subject": "Interview", "message": "Hello!"}'

    Returns:
        dict: Success message and email details

    Raises:
        HTTPException: 404 if candidate not found, 400 for missing fields
    """
    candidate = people_manager.get_single("candidate_id", candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate Not found")

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

    email_entry = email_manager.send_email(
        candidate_id=candidate_id,
        candidate_email=candidate_email,
        recruiter_email=recruiter_email,
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
    return email_manager.get_list("candidate_id", candidate_id)


@app.get("/emails/recruiter")
async def get_recruiter_emails(
    recruiter_email: str = Query(..., description="Email address of the recruiter"),
):
    """
    Get all emails sent by a specific recruiter.

    Args:
        recruiter_email (str): Email of the recruiter

    Example:
        curl -X GET "http://localhost:8000/emails/recruiter?recruiter_email=recruiter@company.com"

    Returns:
        dict: Message and list of emails
    """
    emails = email_manager.get_emails_by_from(recruiter_email)
    if not emails:
        return {
            "message": f"No emails found from recruiter: {recruiter_email}",
            "emails": [],
        }
    return {
        "message": f"Found {len(emails)} emails from recruiter: {recruiter_email}",
        "emails": emails,
    }


@app.get("/emails/recruiter/replies")
async def get_recruiter_email_replies(
    recruiter_email: str = Query(..., description="Email address of the recruiter"),
):
    """
    Get all email replies received for a specific recruiter.

    Args:
        recruiter_email (str): Email of the recruiter

    Example:
        curl -X GET "http://localhost:8000/emails/recruiter/replies?recruiter_email=recruiter@company.com"

    Returns:
        dict: Message and list of email replies
    """
    emails = email_manager.get_emails_by_from(recruiter_email)
    replies = [email for email in emails if email["response"] is not None]

    if not replies:
        return {
            "message": f"No email replies found for recruiter: {recruiter_email}",
            "replies": [],
        }
    return {
        "message": f"Found {len(replies)} email replies for recruiter: {recruiter_email}",
        "replies": replies,
    }


@app.post("/send-sms/{candidate_id}")
async def send_sms(candidate_id: int, request: Request):
    """
    Send an SMS to a candidate.

    Args:
        candidate_id (int): ID of the candidate to message

    Request Body:
        - to (str): Recipient phone number (candidate's phone)
        - from (str): Sender phone number (recruiter's phone)
        - message (str): SMS message content

    Example:
        curl -X POST "http://localhost:8000/send-sms/1" \
          -H "Content-Type: application/json" \
          -d '{"to": "+1234567890", "from": "+1987654321", "message": "Hello!"}'

    Returns:
        dict: Success message and SMS details

    Raises:
        HTTPException: 404 if candidate not found, 400 for missing fields
    """
    candidate = people_manager.get_single("candidate_id", candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate Not found")

    data = await request.json()
    candidate_phone = data.get("to")
    recruiter_phone = data.get("from")
    message = data.get("message")

    if not candidate_phone or not recruiter_phone or not message:
        raise HTTPException(
            status_code=400, detail="Missing required fields: to, from, message"
        )

    sms_entry = sms_manager.send_sms(
        candidate_id=candidate_id,
        candidate_phone=candidate_phone,
        recruiter_phone=recruiter_phone,
        message=message,
    )

    return {"message": f"SMS sent to {candidate['name']}", "sms": sms_entry}


@app.get("/sms")
async def list_sms(
    candidate_id: int | None = Query(None, description="Filter by candidate_id"),
):
    """
    List all SMS messages, optionally filtered by candidate.

    Args:
        candidate_id (int, optional): Filter SMS by candidate ID

    Examples:
        # Get all SMS messages
        curl -X GET "http://localhost:8000/sms"

        # Get SMS for specific candidate
        curl -X GET "http://localhost:8000/sms?candidate_id=1"

    Returns:
        list: List of SMS dictionaries
    """
    sms_list = sms_manager.get_list()
    if candidate_id:
        sms_list = [s for s in sms_list if s["candidate_id"] == candidate_id]
    return sms_list


@app.get("/sms/recruiter")
async def get_recruiter_sms(
    recruiter_phone: str = Query(..., description="Phone number of the recruiter"),
):
    """
    Get all SMS messages sent by a specific recruiter.

    Args:
        recruiter_phone (str): Phone number of the recruiter

    Example:
        curl -X GET "http://localhost:8000/sms/recruiter?recruiter_phone=%2B1987654321"

    Returns:
        dict: Message and list of SMS messages
    """
    sms_list = sms_manager.get_sms_by_recruiter(recruiter_phone)
    if not sms_list:
        return {
            "message": f"No SMS messages found from recruiter: {recruiter_phone}",
            "sms": [],
        }
    return {
        "message": f"Found {len(sms_list)} SMS messages from recruiter: {recruiter_phone}",
        "sms": sms_list,
    }


@app.get("/sms/recruiter/replies")
async def get_recruiter_sms_replies(
    recruiter_phone: str = Query(..., description="Phone number of the recruiter"),
):
    """
    Get all SMS replies received for a specific recruiter.

    Args:
        recruiter_phone (str): Phone number of the recruiter

    Example:
        curl -X GET "http://localhost:8000/sms/recruiter/replies?recruiter_phone=%2B1987654321"

    Returns:
        dict: Message and list of SMS replies
    """
    sms_list = sms_manager.get_sms_by_recruiter(recruiter_phone)
    replies = [sms for sms in sms_list if sms["response"] is not None]

    if not replies:
        return {
            "message": f"No SMS replies found for recruiter: {recruiter_phone}",
            "replies": [],
        }
    return {
        "message": f"Found {len(replies)} SMS replies for recruiter: {recruiter_phone}",
        "replies": replies,
    }


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    # Set uvicorn loggers to WARNING level to reduce noise
    # logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True  # Disable access logs

    logger.info("Starting People Server...")
    uvicorn.run(
        "people_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_config=None,  # Disable uvicorn's default logging config
        access_log=False,  # Disable uvicorn access logs
    )
