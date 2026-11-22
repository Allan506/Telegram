"""Bucle principal: long polling, despacho de comandos, parada ordenada y reinicio."""

from __future__ import annotations

import json
import logging
import random
import signal
import threading
import time
from pathlib import Path
from typing import Any

import requests

from .api import TelegramApi, TelegramError
from .commands import REGISTRY, unknown_command_text
from .config import Config
from .context import Context

log = logging.getLogger(__name__)

GITHUB_DISPATCH_PATH = "/repos/{repo}/actions/workflows/{workflow}/dispatches"


class Bot:
    def __init__(self, api: TelegramApi, config: Config, sleep=time.sleep, clock=time.monotonic) -> None:
        self.api = api
        self.config = config
        self._sleep = sleep
        self._clock = clock
        self.offset: int | None = None
        self.updates_processed = 0
        self.started_at = time.time()
        self._started_monotonic = clock()
        self.stop_event = threading.Event()
        self.load_state()

    def load_state(self) -> None:
        if not self.config.state_file:
            return
        try:
            data = json.loads(Path(self.config.state_file).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            log.warning("No se pudo leer el estado de %s", self.config.state_file, exc_info=True)
            return
        offset = data.get("offset")
        if isinstance(offset, int) and offset > 0:
            self.offset = offset
            log.info("Estado restaurado desde %s (offset=%s)", self.config.state_file, offset)

    def save_state(self) -> None:
        if not self.config.state_file or self.offset is None:
            return
        path = Path(self.config.state_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps({"offset": self.offset, "saved_at": time.time()}), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            log.warning("No se pudo guardar el estado en %s", path, exc_info=True)

    def install_signal_handlers(self) -> None:
        def handle(signum, _frame):
            log.info("Señal %s recibida: cerrando el bot", signum)
            self.stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, handle)
            except (ValueError, OSError):
                log.debug("No se pudo registrar el manejador para %s", sig)

    def drain_pending(self) -> None:
        """Marca como leídas las actualizaciones antiguas para no responder mensajes viejos."""
        try:
            updates = self.api.get_updates(offset=-1, timeout=0, limit=1)
        except (TelegramError, requests.RequestException) as exc:
            log.warning("No se pudieron drenar las actualizaciones pendientes: %s", exc)
            return
        if updates:
            last = max(int(u.get("update_id", 0)) for u in updates)
            self.offset = last + 1
            log.info("Drenadas actualizaciones antiguas (último update_id=%s)", last)

    def _backoff(self, failures: int) -> None:
        delay = min(30.0, 2.0**failures) * (0.5 + random.random())
        log.info("Esperando %.1fs antes de reintentar", delay)
        self.stop_event.wait(delay)

    def poll_once(self, poll_timeout: int | None = None) -> int:
        """Consulta una tanda de actualizaciones y las procesa. Devuelve cuántas procesó."""
        timeout = self.config.poll_timeout if poll_timeout is None else poll_timeout
        updates = self.api.get_updates(offset=self.offset, timeout=timeout)
        for update in updates:
            self.offset = int(update.get("update_id", 0)) + 1
            try:
                self.handle_update(update)
            except Exception:
                log.exception("Error inesperado procesando la actualización %s", update.get("update_id"))
            self.updates_processed += 1
        if updates:
            self.save_state()
        return len(updates)

    def run(self) -> None:
        log.info(
            "Bot arrancando (poll_timeout=%ss, runtime_max=%ss, drain=%s)",
            self.config.poll_timeout,
            self.config.max_runtime_seconds or "∞",
            self.config.drain_on_start,
        )
        self.install_signal_handlers()
        if self.offset is None and self.config.drain_on_start:
            self.drain_pending()

        deadline = None
        if self.config.max_runtime_seconds:
            deadline = self._started_monotonic + self.config.max_runtime_seconds

        failures = 0
        while not self.stop_event.is_set():
            remaining = None if deadline is None else deadline - self._clock()
            if remaining is not None and remaining <= 0:
                log.info("Se alcanzó el tiempo máximo de ejecución")
                break
            poll_timeout = self.config.poll_timeout
            if remaining is not None:
                poll_timeout = max(1, min(poll_timeout, int(remaining)))
            try:
                self.poll_once(poll_timeout)
                failures = 0
            except (TelegramError, requests.RequestException) as exc:
                failures += 1
                log.warning("Fallo consultando Telegram (%s): %s", failures, exc)
                self._backoff(failures)

        log.info("Bot detenido tras procesar %s actualizaciones", self.updates_processed)
        if self.config.self_restart:
            self.trigger_restart()

    def trigger_restart(self) -> None:
        url = self.config.github_api_base + GITHUB_DISPATCH_PATH.format(
            repo=self.config.github_repository, workflow=self.config.github_workflow
        )
        headers = {
            "Authorization": f"Bearer {self.config.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            response = requests.post(url, json={"ref": self.config.github_ref}, headers=headers, timeout=20)
        except requests.RequestException as exc:
            log.error("No se pudo solicitar el reinicio del workflow: %s", exc)
            return
        if response.status_code == 204:
            log.info("Reinicio solicitado: nueva ejecución de %s en camino", self.config.github_workflow)
        else:
            log.error("GitHub rechazó el reinicio (%s): %s", response.status_code, response.text[:300])

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = (message.get("chat") or {}).get("id")
        sender = message.get("from") or {}
        user_id = sender.get("id")
        if chat_id is None:
            return

        if self.config.allowed_user_ids and user_id not in self.config.allowed_user_ids:
            log.info("Acceso denegado al usuario %s (chat %s)", user_id, chat_id)
            self._reply(chat_id, message.get("message_id"), "⛔ No tienes permiso para usar este bot.")
            return

        text = (message.get("text") or "").strip()
        if not text.startswith("/"):
            log.debug("Mensaje sin comando ignorado en el chat %s", chat_id)
            return

        head, _, raw_args = text.partition(" ")
        name = head[1:].split("@", 1)[0].lower()
        command = REGISTRY.get(name)
        if command is None:
            self._reply(chat_id, message.get("message_id"), unknown_command_text(name))
            return

        ctx = Context(
            api=self.api,
            config=self.config,
            chat_id=chat_id,
            user_id=user_id,
            username=sender.get("username") or sender.get("first_name") or "",
            text=text,
            raw_args=raw_args.strip(),
            args=raw_args.split(),
            started_at=self.started_at,
            stats={"updates_processed": self.updates_processed},
        )

        try:
            answer = command.handler(ctx)
        except Exception:
            log.exception("Error ejecutando /%s", name)
            self._reply(chat_id, message.get("message_id"), "⚠️ Ocurrió un error al procesar tu comando.")
            return

        if answer:
            self._reply(chat_id, message.get("message_id"), answer)

    def _reply(self, chat_id: int, message_id: int | None, text: str) -> None:
        try:
            self.api.send_message(chat_id, text, reply_to_message_id=message_id)
        except (TelegramError, requests.RequestException) as exc:
            log.error("No se pudo enviar el mensaje al chat %s: %s", chat_id, exc)
