from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from rich.pretty import pprint

load_dotenv()


def get_chat_client(client_type: str, **kwargs) -> "IChatClient":
    client_type = client_type.lower()
    if client_type == "openai":
        return OpenAIChatClient(**kwargs)
    if client_type == "ollama":
        return OllamaChatClient(**kwargs)
    raise ValueError(f"Unknown chat client type: {client_type}")


class IChatClient(ABC):
    @abstractmethod
    async def get_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_token_cost(self) -> float:
        pass


class OllamaChatClient(IChatClient):
    def __init__(self, model: str = "llama3.2"):
        import ollama

        self.model = model
        self.client = ollama.AsyncClient()

    async def get_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        try:
            response = await self.client.chat(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
            )

            tool_calls = []
            if (
                hasattr(response, "message")
                and hasattr(response.message, "tool_calls")
                and response.message.tool_calls
            ):
                for tool_call in response.message.tool_calls:
                    tool_calls.append(
                        {
                            "id": getattr(tool_call, "id", ""),
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments or {},
                            },
                        }
                    )

            response_text = (
                getattr(response.message, "content", "")
                if hasattr(response, "message")
                else ""
            )

            token_count = sum(
                len(m.get("content", "").split()) for m in messages
            ) + len(response_text.split())

            result = {
                "text": response_text,
                "tool_calls": tool_calls,
                "metadata": {
                    "Usage": {"TotalTokenCount": token_count},
                    "model": self.model,
                },
            }
            return result

        except Exception as e:
            print(f"Error calling Ollama: {e}")
            return {
                "text": f"Error: {str(e)}",
                "tool_calls": [],
                "metadata": {
                    "Usage": {"TotalTokenCount": 0},
                    "model": self.model,
                },
            }

    def get_token_cost(self) -> float:
        return 0.0


class OpenAIChatClient(IChatClient):
    def __init__(self, model: str = "gpt-4o", max_tokens: int = 1000):
        import os

        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def get_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        import asyncio

        loop = asyncio.get_event_loop()

        def sync_call():
            return self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=messages,
                tools=tools,
            )

        completion = await loop.run_in_executor(None, sync_call)
        message = completion.choices[0].message if completion.choices else {}
        text = message.content if hasattr(message, "content") else ""
        token_count = completion.usage.total_tokens if completion.usage else None

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_calls = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in message.tool_calls
            ]

        return {
            "text": text,
            "tool_calls": tool_calls,
            "metadata": {
                "Usage": {"TotalTokenCount": token_count},
                "model": self.model,
            },
        }

    def get_token_cost(self) -> float:
        pricing = {
            "gpt-4": 0.03,  # $0.03 per 1K tokens
            "gpt-4o": 0.03,  # Assuming same pricing as gpt-4
            "gpt-3.5-turbo": 0.002,  # $0.002 per 1K tokens
        }
        return pricing.get(self.model.lower(), 0.0)
