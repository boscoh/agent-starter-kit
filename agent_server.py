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
    logger.info("check_jobs_loop: init")
    while not stop_event.is_set():
        try:
            await agent.check_jobs()
        except Exception as e:
            logger.error(f"Error in job checking loop: {str(e)}", exc_info=True)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3)
        except asyncio.TimeoutError:
            pass


async def check_email_replies_loop(stop_event: asyncio.Event):
    logger.info("check_email_replies_loop: init")
    while not stop_event.is_set():
        try:
            await agent.check_candidates_replies()
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
    logger.debug("Serving agent.html")
    return FileResponse("agent.html")


@app.get("/tools")
async def get_tools():
    logger.debug("Fetching available tools")
    return await agent.get_tools()


@app.get("/state")
async def get_state():
    logger.debug("Fetching application state")
    return agent.get_state()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    logging.getLogger("uvicorn").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").disabled = True

    logger.info("Starting Agent Server...")
    uvicorn.run(
        f"{Path(__file__).stem}:app",
        host="0.0.0.0",
        port=3000,
        reload=True,
        log_config=None,
        log_level=logging.ERROR,
    )
