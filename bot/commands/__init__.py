"""Paquete de comandos. Importarlo registra todos los comandos."""

from .registry import REGISTRY, Command, command, help_text, unknown_command_text
from . import basic, fun, weather  # noqa: F401  (registra los comandos al importar)

__all__ = ["REGISTRY", "Command", "command", "help_text", "unknown_command_text"]
