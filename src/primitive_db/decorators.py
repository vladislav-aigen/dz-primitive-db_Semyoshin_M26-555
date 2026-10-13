"""Error handling, confirmation, timing and closure-based caching."""

import time

from primitive_db.constants import CACHE_LIMIT


def preserve_metadata(wrapper, wrapped):
    """Preserve function metadata without additional standard libraries."""
    wrapper.__name__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    wrapper.__module__ = wrapped.__module__
    wrapper.__wrapped__ = wrapped
    return wrapper


def handle_db_errors(func):
    """Report database errors and return None on failure."""

    def wrapper(*args, **kwargs):
        """Run an operation with centralized error handling."""
        try:
            return func(*args, **kwargs)
        except FileNotFoundError:
            print(
                "Ошибка: Файл данных не найден. "
                "Возможно, база данных не инициализирована."
            )
        except KeyError as error:
            print(f"Ошибка: Таблица или столбец {error} не найден.")
        except ValueError as error:
            print(f"Ошибка валидации: {error}")
        except OSError as error:
            print(f"Ошибка файловой системы: {error}")
        except Exception as error:
            print(f"Произошла непредвиденная ошибка: {error}")
        return None

    return preserve_metadata(wrapper, func)


def confirm_action(action_name):
    """Build a decorator requiring explicit confirmation of an action."""

    def decorator(func):
        """Wrap a destructive function."""

        def wrapper(*args, **kwargs):
            """Cancel unless the user enters y."""
            answer = input(f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: ')
            if answer.strip().lower() != "y":
                print("Операция отменена.")
                return None
            return func(*args, **kwargs)

        return preserve_metadata(wrapper, func)

    return decorator


def log_time(func):
    """Print elapsed monotonic time, including unsuccessful calls."""

    def wrapper(*args, **kwargs):
        """Measure the wrapped operation."""
        started = time.monotonic()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - started
            print(f"Функция {func.__name__} выполнилась за {elapsed:.3f} секунд")

    return preserve_metadata(wrapper, func)


def create_cacher():
    """Return a memoizer with a bounded private dictionary in its closure."""
    cache = {}

    def cache_result(key, value_func):
        """Compute missing entries; do not cache failed computations."""
        if key not in cache:
            value = value_func()
            if len(cache) >= CACHE_LIMIT:
                del cache[next(iter(cache))]
            cache[key] = value
        return cache[key]

    return cache_result
