"""Interactive command dispatch, persistence and presentation."""

import prompt
from prettytable import PrettyTable

from primitive_db import core
from primitive_db.constants import COMMAND_PROMPT, HELP_TEXT, ID_COLUMN, META_FILE
from primitive_db.decorators import handle_db_errors
from primitive_db.parser import parse_command
from primitive_db.utils import (
    load_metadata,
    load_table_data,
    remove_table_data,
    save_metadata,
    save_table_data,
)


def print_help():
    """Print supported commands."""
    print(HELP_TEXT)


def display_rows(schema, rows):
    """Display a result, retaining headers for empty selections."""
    table = PrettyTable()
    table.field_names = list(schema)
    for row in rows:
        table.add_row([row[column] for column in schema])
    print(table)


def manage_tables(operation, metadata, table_name, payload):
    """Persist successful table creation or confirmed removal."""
    if operation == "create_table":
        changed = core.create_table(metadata, table_name, payload)
        if changed is not None:
            save_table_data(table_name, [])
            save_metadata(META_FILE, changed)
            columns = ", ".join(
                f"{key}:{value}" for key, value in changed[table_name].items()
            )
            print(f'Таблица "{table_name}" успешно создана со столбцами: {columns}')
    else:
        if table_name not in metadata:
            raise KeyError(table_name)
        changed = core.drop_table(metadata, table_name)
        if changed is not None:
            remove_table_data(table_name)
            save_metadata(META_FILE, changed)
            print(f'Таблица "{table_name}" успешно удалена.')


def execute_crud(operation, metadata, table_name, payload):
    """Validate commands against the schema and persist only successful results."""
    schema = metadata[table_name]
    if operation == "insert":
        changed = core.insert(metadata, table_name, payload)
        if changed is not None:
            save_table_data(table_name, changed)
            print(
                f"Запись с ID={changed[-1][ID_COLUMN]} успешно добавлена "
                f'в таблицу "{table_name}".'
            )
        return
    rows = load_table_data(table_name)
    if operation == "info":
        print(f"Таблица: {table_name}")
        print(
            "Столбцы: " + ", ".join(f"{key}:{value}" for key, value in schema.items())
        )
        print(f"Количество записей: {len(rows)}")
        return
    condition = payload[1] if operation == "update" else payload
    core.validate_fields(schema, condition or {})
    if operation == "select":
        selected = core.select(rows, condition)
        if selected is not None:
            display_rows(schema, selected)
        return
    if operation == "update":
        changes, condition = payload
        core.validate_fields(schema, changes, allow_id=False)
        changed = core.update(rows, changes, condition)
        verb = "обновлена"
    else:
        changed = core.delete(rows, condition)
        verb = "удалена"
    if changed is not None:
        save_table_data(table_name, changed)
        affected = [row for row in rows if core.matches(row, condition)]
        for row in affected:
            print(
                f'Запись с ID={row[ID_COLUMN]} в таблице "{table_name}" успешно {verb}.'
            )
        if not affected:
            print("Подходящих записей не найдено.")


@handle_db_errors
def execute(command):
    """Handle one command and return False only for an explicit exit."""
    operation, table_name, payload = parse_command(command)
    if operation == "exit":
        return False
    if operation == "empty":
        return True
    if operation == "help":
        print_help()
        return True
    metadata = load_metadata()
    if operation == "list_tables":
        names = core.list_tables(metadata)
        print("\n".join(f"- {name}" for name in names) or "Таблиц пока нет.")
    elif operation in ("create_table", "drop_table"):
        manage_tables(operation, metadata, table_name, payload)
    else:
        execute_crud(operation, metadata, table_name, payload)
    return True


def run():
    """Keep accepting commands after errors; terminate cleanly on EOF/Ctrl-C."""
    print_help()
    try:
        while True:
            command = prompt.string(COMMAND_PROMPT)
            if execute(command) is False:
                break
    except (EOFError, KeyboardInterrupt):
        print("\nДо свидания!")
