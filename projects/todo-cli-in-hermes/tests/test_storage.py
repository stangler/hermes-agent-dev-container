import json
from src.storage import load_todos, save_todos

def test_load_empty_file(tmp_path):
    # 空の JSON ファイルを作成
    file_path = tmp_path / "todos.json"
    file_path.write_text("[]")
    todos = load_todos(str(file_path))
    assert todos == []