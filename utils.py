import json
import re
from datetime import datetime
from typing import TypeVar

T = TypeVar("T")


def parse_json_from_response(response: str):
    # Handle case where response starts with a tool call
    tool_call_match = re.search(
        r"\[Calling tool .+ with args \{.*\}\]([\s\S]*)", response
    )
    if tool_call_match:
        response = tool_call_match.group(1).strip()

    try:
        # Handle code block format
        json_match = re.search(r"```(?:json\n)?([\s\S]*?)```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        return json.loads(json_str)
    except Exception:
        return response.strip()


def _current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
