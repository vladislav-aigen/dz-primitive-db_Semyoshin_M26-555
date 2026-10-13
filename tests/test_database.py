"""Behavioral regression tests for persistence, commands and decorators."""

import builtins
import json
import os
import subprocess

import pytest

from primitive_db import core
from primitive_db.decorators import create_cacher, handle_db_errors, log_time
from primitive_db.engine import execute
from primitive_db.parser import parse_command, parse_values, parse_where
from primitive_db.utils import load_metadata, load_table_data


@pytest.fixture
def database(tmp_path, monkeypatch):
    """Give each test isolated persistent storage."""
    monkeypatch.chdir(tmp_path)
    assert execute("create_table users name:str age:int active:bool") is True
    return tmp_path


def test_full_crud_and_confirmation(database, monkeypatch, capsys):
    """Exercise mutations, denied actions and confirmed destructive actions."""
    execute('insert into users values ("Ada Lovelace", 28, true)')
    execute("select from users where age=28")
    assert "Ada Lovelace" in capsys.readouterr().out
    execute('update users set age=29 where name="Ada Lovelace"')
    assert load_table_data("users")[0]["age"] == 29
    execute("select from users where age=28")
    assert "Ada Lovelace" not in capsys.readouterr().out
    monkeypatch.setattr(builtins, "input", lambda _: "n")
    execute("delete from users where ID=1")
    execute("drop_table users")
    assert len(load_table_data("users")) == 1
    assert "users" in load_metadata()
    monkeypatch.setattr(builtins, "input", lambda _: "y")
    execute("delete from users where ID=1")
    assert load_table_data("users") == []
    execute("drop_table users")
    assert load_metadata() == {}
    assert not (database / "data/users.json").exists()


@pytest.mark.parametrize(
    "command",
    [
        'insert into users values ("Ada", true, true)',
        'insert into users values ("Ada", 1)',
        "insert into users values (Ada, 1, false)",
        'update users set age="bad" where ID=1',
        "update users set ID=99 where ID=1",
        "update users set missing=1 where ID=1",
        "delete from users where missing=1",
        "select from users where age=true",
        "select from users where age==1",
    ],
)
def test_invalid_commands_do_not_change_data(database, command, capsys):
    """Type and grammar failures must not modify persisted rows."""
    execute('insert into users values ("Ada", 1, true)')
    before = (database / "data/users.json").read_bytes()
    assert execute(command) is not False
    assert (database / "data/users.json").read_bytes() == before
    assert "Ошибка" in capsys.readouterr().out


def test_missing_file_is_not_silently_recreated(database, capsys):
    """A lost data file is an error rather than an empty database."""
    (database / "data/users.json").unlink()
    execute("select from users")
    assert "Файл данных не найден" in capsys.readouterr().out
    assert not (database / "data/users.json").exists()


def test_corrupt_json_is_not_overwritten(database, capsys):
    """Report invalid JSON and retain the damaged file for recovery."""
    path = database / "data/users.json"
    path.write_text("{broken")
    execute('insert into users values ("Ada", 1, true)')
    assert path.read_text() == "{broken"
    assert "Ошибка валидации" in capsys.readouterr().out


def test_id_after_nonterminal_deletion(database, monkeypatch):
    """Deleting an earlier row must not cause duplicate generated IDs."""
    for name in ["a", "b", "c"]:
        execute(f'insert into users values ("{name}", 1, false)')
    monkeypatch.setattr(builtins, "input", lambda _: "y")
    execute("delete from users where ID=2")
    execute('insert into users values ("d", 1, true)')
    assert [row["ID"] for row in load_table_data("users")] == [1, 3, 4]


def test_invalid_schema_and_path(database):
    """Reject duplicate columns, unknown types and path traversal."""
    original = load_metadata()
    for name, columns in [
        ("../outside", ["name:str"]),
        ("bad", ["value:float"]),
        ("bad", ["name:str", "name:int"]),
        ("bad", ["ID:int"]),
    ]:
        assert core.create_table(original, name, columns) is None
    assert original == load_metadata()


def test_parser_preserves_strings():
    """Quoted punctuation and keywords are literal values."""
    assert parse_values('("Ada, where = (x)", -2, false)') == [
        "Ada, where = (x)",
        -2,
        False,
    ]
    assert parse_where("name = 'true'") == {"name": "true"}
    assert parse_command('update t set name="where" where ID=1')[2] == (
        {"name": "where"},
        {"ID": 1},
    )


def test_cache_hit_and_snapshot_invalidation():
    """Reuse computations but never leak mutable cached rows."""
    cache = create_cacher()
    calls = []

    def compute():
        """Track real cache misses."""
        calls.append(1)
        return None

    assert cache("key", compute) is None
    assert cache("key", compute) is None
    assert len(calls) == 1
    rows = [{"ID": 1, "age": 20}]
    selected = core.select(rows, {"age": 20})
    selected[0]["age"] = 99
    assert core.select(rows, {"age": 20}) == [{"ID": 1, "age": 20}]
    rows[0]["age"] = 21
    assert core.select(rows, {"age": 20}) == []
    rows.append({"ID": 2, "age": 20})
    assert core.select(rows, {"age": 20}) == [{"ID": 2, "age": 20}]


@pytest.mark.parametrize(
    "error", [KeyError("missing"), ValueError("bad"), FileNotFoundError("lost")]
)
def test_error_decorator(error, capsys):
    """Known errors become readable diagnostics."""

    @handle_db_errors
    def failing():
        """Raise a selected database error."""
        raise error

    assert failing() is None
    assert "Ошибка" in capsys.readouterr().out
    assert failing.__name__ == "failing"


def test_timer(capsys, monkeypatch):
    """Use monotonic time and retain the original function name."""
    ticks = iter([10.0, 10.125])
    monkeypatch.setattr("primitive_db.decorators.time.monotonic", lambda: next(ticks))

    @log_time
    def sample():
        """Return a value through the decorator."""
        return 42

    assert sample() == 42
    assert "Функция sample выполнилась за 0.125 секунд" in capsys.readouterr().out


def test_relaunch_persists_and_cli_recovers(database):
    """Run the installed executable across two independent sessions."""
    command = os.path.join(os.path.dirname(os.sys.executable), "database")
    first = subprocess.run(
        [command],
        input='insert into users values ("Saved", 42, true)\nexit\n',
        text=True,
        capture_output=True,
        check=True,
    )
    assert "успешно добавлена" in first.stdout
    second = subprocess.run(
        [command],
        input="nonsense\nselect from users\nexit\n",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Ошибка валидации" in second.stdout
    assert "Saved" in second.stdout
    assert json.loads((database / "data/users.json").read_text())[0]["age"] == 42
