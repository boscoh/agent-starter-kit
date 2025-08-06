import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

from path import Path

T = TypeVar("T")


def parse_json_from_response(response: str):
    # Handle case where response starts with a tool call
    tool_call_match = re.search(r'\[Calling tool .+ with args \{\}\]([\s\S]*)', response)
    if tool_call_match:
        response = tool_call_match.group(1).strip()
    
    # Handle code block format
    json_match = re.search(r"```(?:json\n)?([\s\S]*?)```", response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        json_str = response.strip()
    
    # Clean up any remaining markdown formatting
    json_str = re.sub(r'^[\s\-*]+', '', json_str, flags=re.MULTILINE)
    
    return json.loads(json_str)


def load_json_file(
    filepath: Union[str, Path], model: Type[T] = None
) -> Union[dict, list, T]:
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if filepath.stat().st_size == 0:
        return [] if model is None else []

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if model is not None:
        if isinstance(data, list):
            return [model.model_validate(item) for item in data]
        return model.model_validate(data)
    return data


def save_json_file(
    filepath: Union[str, Path],
    data: Any,
    indent: int = 2,
) -> None:
    filepath = Path(filepath)
    if filepath.parent:
        filepath.parent.makedirs_p()

    with open(filepath, "w", encoding="utf-8") as f:
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
            data = [item.model_dump() for item in data]

        json.dump(data, f, indent=indent)


def _current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
