"""Contexto que recibe cada comando."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .api import TelegramApi


@dataclass
class Context:
    api: TelegramApi
    config: Any
    chat_id: int
    user_id: int
    username: str
    text: str
    raw_args: str
    args: list[str]
    started_at: float
    stats: dict[str, Any] = field(default_factory=dict)
