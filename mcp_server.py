"""MCP (Model-Controller-Presenter) Server for a job candidate matching system.

This module implements a FastMCP server that provides API endpoints for managing job postings,
candidate information, and weather forecasts. It serves as the backend for a job matching
platform, allowing clients to interact with the system through Server-Sent Events (SSE).

The server exposes the following main functionalities:
- Job management (listing available jobs, updating job status)
- Candidate management (listing candidates, updating availability)
- Weather forecast retrieval for location-based services

Example:
    To start the server:
    ```bash
    python mcp_server.py --host 0.0.0.0 --port 8080
    ```

Note:
    The server uses Starlette as the ASGI framework and uvicorn as the ASGI server.
    It's configured with rich logging for better development experience.
"""

import logging

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from rich.logging import RichHandler
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from candidates import CandidateStore
from jobs import JobStore
from weather import get_forecast

logger = logging.getLogger(__name__)

mcp = FastMCP("mvp")
job_store = JobStore()
candidate_store = CandidateStore()


@mcp.tool()
async def get_candidates() -> list[dict]:
    """Retrieves all candidates who are currently available for work.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary contains information
                  about an available candidate. Each candidate dictionary includes
                  details such as candidate_id, name, skills, and availability status.
    """
    candidates = candidate_store.get_list()
    candidates = candidates.copy()
    for candidate in candidates:
        del candidate["messages"]
        del candidate["job_id"]
    return candidates


@mcp.tool()
async def get_forecast_tool(latitude: float, longitude: float) -> str:
    """Retrieves weather forecast for the specified geographic coordinates.

    Args:
        latitude: The latitude coordinate (decimal degrees, -90 to 90).
        longitude: The longitude coordinate (decimal degrees, -180 to 180).

    Returns:
        str: A formatted string containing the weather forecast for the specified
             location, including current conditions and upcoming weather predictions.
    """
    return get_forecast(latitude, longitude)


def create_starlette_app(mcp: FastMCP, *, debug: bool = False) -> Starlette:
    logger.info("Creating Starlette app with debug=%s", debug)

    mcp_server = mcp._mcp_server  # noqa: WPS437

    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        logger.info(
            "SSE connection established from %s",
            request.client if hasattr(request, "client") else "unknown client",
        )
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            logger.info("Starting MCP server stream handler.")
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
            logger.info("MCP server stream handler completed.")

    app = Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )
    logger.info("Starlette app created and routes registered.")
    return app


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run MCP SSE-based server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, omit_repeated_times=False)],
    )

    # Disable Starlette's logging
    logging.getLogger("starlette").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    starlette_app = create_starlette_app(mcp, debug=True)

    uvicorn.run(
        starlette_app,
        host=args.host,
        port=args.port,
        log_config=None,  # Disable uvicorn's default logging config
    )
