"""Shared application settings."""

META_FILE = "db_meta.json"
DATA_DIR = "data"
ENCODING = "utf-8"
VALID_TYPES = {"int": int, "str": str, "bool": bool}
ID_COLUMN = "ID"
CACHE_LIMIT = 128
COMMAND_PROMPT = ">>> Введите команду: "
HELP_TEXT = """***База данных***
create_table <таблица> <столбец:тип> ... — создать таблицу
list_tables — список таблиц
drop_table <таблица> — удалить таблицу (с подтверждением)
insert into <таблица> values (<значение>, ...) — добавить запись
select from <таблица> [where <столбец> = <значение>] — выборка
update <таблица> set <столбец> = <значение> where <столбец> = <значение>
delete from <таблица> where <столбец> = <значение> — удалить записи
info <таблица> — схема и количество записей
Типы: int, str, bool. Строки — в кавычках, bool — true/false.
help — справка; exit — выход"""
