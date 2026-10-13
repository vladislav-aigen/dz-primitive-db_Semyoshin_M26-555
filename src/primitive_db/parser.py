"""Parse a small SQL-like language while preserving quoted literals."""

import shlex


def tokenize(command):
    """Keep quoted strings intact and split punctuation outside quotes."""
    lexer = shlex.shlex(command, posix=False, punctuation_chars="(),=")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = []
    for token in lexer:
        if token and all(char in "(),=" for char in token):
            tokens.extend(token)
        else:
            tokens.append(token)
    return tokens


def parse_value(token):
    """Read quoted str, signed int or true/false; reject implicit strings."""
    if len(token) >= 2 and token[0] in "\"'" and token[-1] == token[0]:
        return shlex.split(token)[0]
    if token.lower() in ("true", "false"):
        return token.lower() == "true"
    if token.lstrip("+-").isascii() and token.lstrip("+-").isdigit():
        return int(token)
    raise ValueError(f"Некорректное значение: {token}. Строки нужны в кавычках.")


def parse_assignment(tokens):
    """Parse exactly one column = literal expression."""
    if len(tokens) != 3 or tokens[1] != "=" or not tokens[0].isidentifier():
        raise ValueError("Ожидается: <столбец> = <значение>.")
    return {tokens[0]: parse_value(tokens[2])}


def parse_where(expression):
    """Convert a where expression to a typed dictionary."""
    return parse_assignment(tokenize(expression))


def parse_set(expression):
    """Convert a set expression to a typed dictionary."""
    return parse_assignment(tokenize(expression))


def parse_values(tokens):
    """Parse a parenthesized comma-separated list of values."""
    if isinstance(tokens, str):
        tokens = tokenize(tokens)
    if len(tokens) < 2 or tokens[0] != "(" or tokens[-1] != ")":
        raise ValueError("Значения должны быть в круглых скобках.")
    inner = tokens[1:-1]
    if not inner:
        return []
    if len(inner) % 2 == 0 or any(t != "," for t in inner[1::2]):
        raise ValueError("Значения должны быть разделены запятыми.")
    return [parse_value(token) for token in inner[::2]]


def parse_command(command):
    """Return (operation, table, payload), rejecting malformed commands."""
    tokens = tokenize(command)
    if not tokens:
        return "empty", None, None
    operation = tokens[0].lower()
    if operation in ("exit", "help", "list_tables") and len(tokens) == 1:
        return operation, None, None
    if operation in ("info", "drop_table") and len(tokens) == 2:
        return operation, tokens[1], None
    if operation == "create_table" and len(tokens) >= 3:
        return operation, tokens[1], tokens[2:]
    if (
        operation == "insert"
        and len(tokens) >= 6
        and tokens[1].lower() == "into"
        and tokens[3].lower() == "values"
    ):
        return operation, tokens[2], parse_values(tokens[4:])
    if (
        operation in ("select", "delete")
        and len(tokens) >= 3
        and tokens[1].lower() == "from"
    ):
        if len(tokens) == 3 and operation == "select":
            return operation, tokens[2], None
        if len(tokens) == 7 and tokens[3].lower() == "where":
            return operation, tokens[2], parse_assignment(tokens[4:])
    if (
        operation == "update"
        and len(tokens) == 10
        and tokens[2].lower() == "set"
        and tokens[6].lower() == "where"
    ):
        return (
            operation,
            tokens[1],
            (parse_assignment(tokens[3:6]), parse_assignment(tokens[7:10])),
        )
    raise ValueError(f"Неизвестная команда или неверный синтаксис: {operation}")
