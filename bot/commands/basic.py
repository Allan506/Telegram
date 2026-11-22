"""Comandos básicos: información del bot, utilidades y diagnóstico."""

from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from html import escape

from .. import __version__
from .registry import command, help_text


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} d")
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    parts.append(f"{secs} s")
    return " ".join(parts)


@command("start", "Mensaje de bienvenida")
def start(ctx):
    name = escape(ctx.username or "hola")
    return (
        f"¡Hola, <b>{name}</b>! 👋\n\n"
        "Soy un bot de Telegram escrito en Python que corre 24/7 en GitHub Actions.\n\n"
        "Escribe /help para ver todo lo que puedo hacer."
    )


@command("help", "Muestra la lista de comandos")
def help_command(ctx):
    return help_text()


@command("ping", "Comprueba que el bot responde")
def ping(ctx):
    started = time.perf_counter()
    ctx.api.get_me()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return f"🏓 Pong — {elapsed_ms:.0f} ms hasta la API de Telegram"


@command("id", "Muestra tu ID de usuario y de chat")
def whoami(ctx):
    return (
        f"👤 ID de usuario: <code>{ctx.user_id}</code>\n"
        f"💬 ID de chat: <code>{ctx.chat_id}</code>\n\n"
        "Usa estos números en la variable <code>ALLOWED_USER_IDS</code> si quieres "
        "restringir el acceso al bot."
    )


@command("echo", "Repite el texto que envíes", "/echo <texto>")
def echo(ctx):
    if not ctx.raw_args:
        return "Uso: <code>/echo &lt;texto&gt;</code>"
    return escape(ctx.raw_args)


@command("hora", "Muestra la fecha y hora actuales")
def hora(ctx):
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()
    return (
        f"🌍 UTC: <code>{now_utc:%Y-%m-%d %H:%M:%S}</code>\n"
        f"🖥️ Servidor: <code>{now_local:%Y-%m-%d %H:%M:%S %Z}</code>"
    )


@command("estado", "Estado y estadísticas del bot")
def estado(ctx):
    uptime = time.time() - ctx.started_at
    processed = ctx.stats.get("updates_processed", 0)
    return (
        "<b>Estado del bot</b>\n"
        f"✅ Activo desde hace {_format_duration(uptime)}\n"
        f"📨 Actualizaciones procesadas: {processed}\n"
        f"🐍 Python {platform.python_version()} en {platform.system()}\n"
        f"🏷️ Versión del bot: {__version__}\n"
        f"🆔 PID: {os.getpid()}\n"
        f"🔧 Estado persistente: {'sí' if ctx.config.state_file else 'no'}"
    )
