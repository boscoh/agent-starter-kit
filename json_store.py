import json
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from path import Path

T = TypeVar("T")


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


T = TypeVar("T", bound=Dict[str, Any])


class JsonListStore(Generic[T]):
    def __init__(self, json_file: Union[str, Path]):
        self.json_file = Path(json_file)
        self.lock_file = self.json_file.parent / f"{self.json_file.name}.lock"
        self.data: List[T] = []
        if self.json_file and self.json_file.exists():
            self.load()

    def load(self, filepath: Union[str, Path] = None) -> None:
        filepath = Path(filepath) if filepath else self.json_file
        if not filepath:
            self.data = []
            return

        try:
            if filepath.exists():
                self.data = load_json_file(filepath)
            else:
                self.data = []
        except Exception as e:
            print(f"Error: reading {filepath}: {e}")
            raise

    def save(self, filepath: Union[str, Path] = None) -> None:
        filepath = Path(filepath) if filepath else self.json_file
        if not filepath:
            return
        try:
            filepath.parent.makedirs_p()
            save_json_file(filepath, self.data)
        except Exception as e:
            print(f"Error: saving {filepath}: {e}")
            raise

    def clear(self) -> None:
        self.data = []
        self.save()

    def get_list(self, field: Optional[str] = None, value: Any = None) -> List[T]:
        self.load()
        if not field:
            return self.data
        return [item for item in self.data if item.get(field) == value]

    def get_single(self, field: str, value: Any) -> Optional[T]:
        self.load()
        for item in self.data:
            if item.get(field) == value:
                return item
        return None
