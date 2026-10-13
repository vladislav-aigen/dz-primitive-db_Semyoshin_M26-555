"""JSON persistence; paths are relative to the launch directory."""

import json
import os

from primitive_db.constants import DATA_DIR, ENCODING, META_FILE


def validate_name(name):
    """Allow identifiers only, preventing traversal outside data/."""
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError(f"Некорректное имя: {name}")
    return name


def table_path(table_name):
    """Return the validated table filename."""
    return os.path.join(DATA_DIR, f"{validate_name(table_name)}.json")


def read_json(filepath):
    """Load JSON, propagating missing or malformed file errors."""
    with open(filepath, encoding=ENCODING) as source:
        return json.load(source)


def write_json(filepath, data):
    """Replace one JSON file atomically after a successful write."""
    temporary = f"{filepath}.tmp"
    try:
        with open(temporary, "w", encoding=ENCODING) as destination:
            json.dump(data, destination, ensure_ascii=False, indent=2)
            destination.write("\n")
        os.replace(temporary, filepath)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def load_metadata(filepath=META_FILE):
    """A missing metadata file denotes a new database."""
    try:
        metadata = read_json(filepath)
    except FileNotFoundError:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("Метаданные должны быть JSON-объектом.")
    return metadata


def save_metadata(filepath, data):
    """Persist the table schemas."""
    write_json(filepath, data)


def load_table_data(table_name):
    """Load rows; an absent table file is an error, not an empty table."""
    data = read_json(table_path(table_name))
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("Данные таблицы должны быть списком записей.")
    return data


def save_table_data(table_name, data):
    """Create the storage directory and persist rows."""
    os.makedirs(DATA_DIR, exist_ok=True)
    write_json(table_path(table_name), data)


def remove_table_data(table_name):
    """Remove a table's persisted rows."""
    os.remove(table_path(table_name))
