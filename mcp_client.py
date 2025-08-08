import asyncio
import functools
import json
import logging
import sys
from contextlib import AsyncExitStack
from typing import Any, Callable, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client
from rich.logging import RichHandler

from chat_client import get_chat_client

logger = logging.getLogger(__name__)


def async_init_prehook(method: Callable) -> Callable:
    @functools.wraps(method)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        await self.check_async_init()
        return await method(self, *args, **kwargs)

    return wrapper


class MCPClient:
    """A client for interacting with an MCP (Model Control Protocol) server via Server-Sent Events (SSE).

    This class provides a client interface to communicate with an MCP server, allowing for:
    - Establishing and managing SSE connections to the MCP server
    - Discovering and listing available tools on the server
    - Processing natural language queries through an integrated chat client
    - Executing appropriate tools based on chat client responses
    - Managing the lifecycle of the connection

    The client integrates with a chat client (defaulting to OpenAI) to process natural language
    queries and determine which tools to call. The chat client handles the natural language
    understanding and tool selection, while this class manages the communication with the MCP server.

    Args:
        mcp_server_url (str, optional): The URL of the MCP server's SSE endpoint.
            Defaults to "http://localhost:8080/sse".
        chat_client_type (str, optional): The type of chat client to use for processing queries.
            Defaults to "openai".

    Attributes:
        session (Optional[ClientSession]): The active MCP client session.
        exit_stack (AsyncExitStack): Manages cleanup of async resources.
        chat_client: The chat client instance for processing natural language.
        server_url (str): The URL of the MCP server.
        is_async_init (bool): Flag indicating if async initialization is complete.

    Example:
        ```python
        async with MCPClient() as client:
            tools = await client.get_tools()
            result = await client.process_query("What's the weather like?")
        ```
    """

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:8080/sse",
        chat_client_type="openai",
    ):
        logger.info("Initializing MCPClient with server URL: %s", mcp_server_url)
        logger.debug("Using chat client type: %s", chat_client_type)

        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.chat_client = get_chat_client(chat_client_type)
        self.server_url = mcp_server_url
        self.is_async_init = False
        self._session_context = None
        self._streams_context = None

    async def check_async_init(self):
        if self.is_async_init:
            return
        await self.connect_to_sse_server()

    async def connect_to_sse_server(self):
        self._streams_context = sse_client(url=self.server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session: ClientSession = await self._session_context.__aenter__()
        await self.session.initialize()
        self.is_async_init = True
        logger.info("Initialized an MCP-SSE client...")

        self.tools = await self.get_tools()
        logger.info("Tools:")
        for tool in self.tools:
            name = tool["function"]["name"]
            logger.info(f"- {name}")

    @async_init_prehook
    async def get_tools(self):
        response = await self.session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in response.tools
        ]

    async def cleanup(self):
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    @async_init_prehook
    async def process_query(self, query: str) -> str:
        messages = [{"role": "user", "content": str(query)}]
        response = await self.chat_client.get_completion(messages, self.tools)

        tool_results = []
        final_text = []

        if not response.get("tool_calls"):
            if response.get("text"):
                final_text.append(str(response["text"]))
        else:
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                if isinstance(tool_call["function"]["arguments"], str):
                    tool_args = json.loads(tool_call["function"]["arguments"])
                else:
                    tool_args = tool_call["function"]["arguments"]

                result = await self.session.call_tool(tool_name, tool_args)

                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                messages.append(
                    {"role": "assistant", "content": f"Tool {tool_name} called."}
                )
                result_content = str(getattr(result, "content", str(result)))
                messages.append({"role": "user", "content": result_content})

                next_response = await self.chat_client.get_completion(messages=messages)

                if next_response.get("text"):
                    final_text.append(str(next_response["text"]))

        return "\n".join(final_text)


async def main():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    mcp_server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/sse"
    client = MCPClient(mcp_server_url, "ollama")
    print("Type your queries or 'quit' to exit.")
    while True:
        query = input("\nQuery: ").strip()
        if query.lower() == "quit":
            break
        try:
            response = await client.process_query(query)
            print(response)
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            print(f"\nError: {str(e)}")
    await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
