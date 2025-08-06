import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from path import Path
from rich.logging import RichHandler

import agent

logger = logging.getLogger(__name__)

app = FastAPI()


async def check_jobs_loop(stop_event: asyncio.Event):
    logger.info("Starting job checking loop")
    while not stop_event.is_set():
        try:
            await agent.check_jobs()
            logger.debug("Completed job check cycle")
        except Exception as e:
            logger.error(f"Error in job checking loop: {str(e)}", exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3)
        except asyncio.TimeoutError:
            pass


async def check_email_replies_loop(stop_event: asyncio.Event):
    logger.info("Starting email replies checking loop")
    while not stop_event.is_set():
        try:
            await agent.check_candidates_replies()
            logger.debug("Completed email replies check cycle")
        except Exception as e:
            logger.error(f"Error in email replies loop: {str(e)}", exc_info=True)

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
        asyncio.create_task(check_jobs_loop(stop_event)),
        asyncio.create_task(check_email_replies_loop(stop_event)),
    ]

    logger.info("Background tasks started")

    try:
        yield
    finally:
        logger.info("Shutting down application...")
        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Background tasks stopped")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_index():
    logger.debug("Serving index.html")
    return FileResponse("index.html")


@app.get("/tools")
async def get_tools():
    logger.info("Fetching available tools")
    return await agent.get_tools()


@app.get("/state")
async def get_state():
    logger.debug("Fetching application state")
    return agent.get_state()


if __name__ == "__main__":
    import argparse

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Agent Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=3000, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    # Configure logging level based on debug flag
    log_level = logging.DEBUG if args.debug else logging.INFO

    logger.info(f"Starting Agent Server on {args.host}:{args.port}")

    # Set uvicorn loggers to WARNING level to reduce noise
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True  # Disable access logs

    uvicorn.run(
        "agent_server:app",
        host=args.host,
        port=args.port,
        reload=args.debug,
        log_config=None,  # Disable uvicorn's default logging config
        log_level=log_level,
    )
