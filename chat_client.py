import asyncio
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import ollama
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
    ChatCompletionFunctionTool,
)

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
                tool_calls = [call.model_dump() for call in response.message.tool_calls]

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
    def __init__(self, model: str = "o4-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    @staticmethod
    def convert_message(msg: Dict[str, Any]):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            return ChatCompletionSystemMessageParam(role=role, content=content)
        elif role == "user":
            return ChatCompletionUserMessageParam(role=role, content=content)
        elif role == "assistant":
            return ChatCompletionAssistantMessageParam(
                role=role,
                content=content,
                tool_calls=msg.get("tool_calls"),
            )
        elif role == "tool":
            return ChatCompletionToolMessageParam(
                role=role,
                content=content,
                tool_call_id=msg.get("tool_call_id"),
            )
        else:
            raise ValueError(f"Unsupported message role: {role}")

    @staticmethod
    def convert_tools(
        tools: Optional[List[Dict[str, Any]]],
    ) -> Optional[List[ChatCompletionToolParam]]:
        if not tools:
            return None
        return [
            ChatCompletionToolParam(
                type="function",
                function={
                    "name": tool["function"]["name"],
                    "description": tool["function"].get("description", ""),
                    "parameters": tool["function"].get("parameters", {}),
                },
            )
            for tool in tools
        ]

    async def get_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:

        def sync_call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[self.convert_message(msg) for msg in messages],
                tools=self.convert_tools(tools),
            )

        loop = asyncio.get_event_loop()
        completion = await loop.run_in_executor(None, sync_call)
        message = completion.choices[0].message if completion.choices else {}
        text = message.content if hasattr(message, "content") else ""
        token_count = completion.usage.total_tokens if completion.usage else None

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_calls = [call.to_dict() for call in message.tool_calls]

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
