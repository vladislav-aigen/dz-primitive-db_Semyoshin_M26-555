"""Procedural table management and CRUD business logic."""

import json

from primitive_db.constants import ID_COLUMN, VALID_TYPES
from primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)
from primitive_db.utils import load_table_data, validate_name

_select_cache = create_cacher()


def validate_fields(schema, fields, allow_id=True):
    """Validate both columns and exact types (bool is not an int)."""
    for column, value in fields.items():
        if column not in schema:
            raise KeyError(column)
        if column == ID_COLUMN and not allow_id:
            raise ValueError("ID генерируется автоматически и не изменяется.")
        if type(value) is not VALID_TYPES[schema[column]]:
            raise ValueError(f"Столбец {column}: требуется {schema[column]}.")


def matches(row, where_clause):
    """Match every condition with strict type equality."""
    return all(
        type(row[column]) is type(value) and row[column] == value
        for column, value in (where_clause or {}).items()
    )


@handle_db_errors
def create_table(metadata, table_name, columns):
    """Validate a schema, prepend ID:int, and return updated metadata."""
    validate_name(table_name)
    if table_name in metadata:
        raise ValueError(f'Таблица "{table_name}" уже существует.')
    schema = {ID_COLUMN: "int"}
    for specification in columns:
        parts = specification.split(":")
        if len(parts) != 2:
            raise ValueError(f"Неверное описание столбца: {specification}")
        name, data_type = parts
        validate_name(name)
        if name in schema:
            raise ValueError(f"Повторный или зарезервированный столбец: {name}")
        if data_type not in VALID_TYPES:
            raise ValueError(f"Неизвестный тип: {data_type}")
        schema[name] = data_type
    return {**metadata, table_name: schema}


@handle_db_errors
@confirm_action("удаление таблицы")
def drop_table(metadata, table_name):
    """Return metadata without the confirmed table."""
    if table_name not in metadata:
        raise KeyError(table_name)
    return {name: schema for name, schema in metadata.items() if name != table_name}


@handle_db_errors
def list_tables(metadata):
    """Return table names in stable order."""
    return sorted(metadata)


@handle_db_errors
@log_time
def insert(metadata, table_name, values):
    """Load rows, validate values and append a generated unique ID."""
    schema = metadata[table_name]
    columns = [name for name in schema if name != ID_COLUMN]
    if len(values) != len(columns):
        raise ValueError(f"Ожидается {len(columns)} значений, получено {len(values)}.")
    row = dict(zip(columns, values, strict=True))
    validate_fields(schema, row)
    rows = load_table_data(table_name)
    row = {ID_COLUMN: max((item[ID_COLUMN] for item in rows), default=0) + 1, **row}
    return [*rows, row]


@handle_db_errors
@log_time
def select(table_data, where_clause=None):
    """Cache selections by the full data snapshot and typed condition."""
    key = json.dumps([table_data, where_clause], sort_keys=True, ensure_ascii=False)
    result = _select_cache(
        key, lambda: [row.copy() for row in table_data if matches(row, where_clause)]
    )
    return [row.copy() for row in result]


@handle_db_errors
def update(table_data, set_clause, where_clause):
    """Return changed rows without partially mutating the input."""
    if ID_COLUMN in set_clause:
        raise ValueError("ID генерируется автоматически и не изменяется.")
    for row in table_data:
        for column, value in set_clause.items():
            if column not in row:
                raise KeyError(column)
            if type(row[column]) is not type(value):
                raise ValueError(f"Неверный тип столбца {column}.")
    return [
        {**row, **set_clause} if matches(row, where_clause) else row.copy()
        for row in table_data
    ]


@handle_db_errors
@confirm_action("удаление записей")
def delete(table_data, where_clause):
    """Return remaining rows after confirmation."""
    if not where_clause:
        raise ValueError("Для удаления необходимо условие where.")
    return [row.copy() for row in table_data if not matches(row, where_clause)]
