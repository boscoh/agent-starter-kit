import os
from typing import Any, Dict, Generic, List, Optional, TypeVar

from utils import load_json_file, save_json_file

T = TypeVar("T", bound=Dict[str, Any])


class JsonListStore(Generic[T]):
    def __init__(self, json_file: str):
        self.json_file = json_file
        self.lock_file = f"{json_file}.lock"
        self.data: List[T] = []
        if self.json_file and os.path.exists(self.json_file):
            self.load()

    def load(self, filepath: str = None) -> None:
        filepath = filepath or self.json_file
        if not filepath:
            self.data = []
            return

        try:
            if os.path.exists(filepath):
                self.data = load_json_file(filepath)
            else:
                self.data = []
        except Exception as e:
            print(f"Error: reading {filepath}: {e}")
            raise

    def save(self, filepath: str = None) -> None:
        filepath = filepath or self.json_file
        if not filepath:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            save_json_file(filepath, self.data)
        except Exception as e:
            print(f"Error: saving {filepath}: {e}")
            raise

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
