"""Registro de comandos: un dict nombre -> Command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..context import Context

Handler = Callable[[Context], "str | list[str] | None"]


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    handler: Handler
    usage: str = ""


REGISTRY: dict[str, Command] = {}


def command(name: str, description: str, usage: str = ""):
    def decorator(func: Handler) -> Handler:
        REGISTRY[name] = Command(name=name, description=description, handler=func, usage=usage)
        return func

    return decorator


def help_text() -> str:
    lines = ["<b>Comandos disponibles</b>", ""]
    for name in sorted(REGISTRY):
        item = REGISTRY[name]
        usage = f" <code>{item.usage}</code>" if item.usage else ""
        lines.append(f"/{item.name}{usage} — {item.description}")
    lines += ["", "Escrito en Python y desplegado en GitHub Actions (24/7)."]
    return "\n".join(lines)


def unknown_command_text(name: str) -> str:
    return (
        f"No conozco el comando <code>/{name}</code>.\n"
        "Escribe /help para ver la lista de comandos."
    )
