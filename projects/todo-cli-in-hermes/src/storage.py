import json
from typing import List, Dict

def load_todos(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_todos(path: str, todos: List[Dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)