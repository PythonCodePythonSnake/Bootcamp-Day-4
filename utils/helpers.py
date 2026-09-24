"""Genuinely shared helper functions used across the project. No agent logic here."""

from __future__ import annotations

import functools
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

T = TypeVar("T")


def load_prompt(name: str) -> str:
    """Load a prompt's text contents from prompts/<name>.txt."""
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()


def with_retry(max_attempts: int = 2, delay_seconds: float = 1.0) -> Callable:
    """Simple retry decorator for flaky external API/tool calls."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt < max_attempts:
                        time.sleep(delay_seconds)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


def safe_get(d: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts: safe_get(d, 'a', 'b') == d.get('a', {}).get('b')."""
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current