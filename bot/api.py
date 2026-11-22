"""Cliente mínimo de la API de Telegram: long polling y envío de mensajes."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

MAX_MESSAGE_LENGTH = 4000
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

log = logging.getLogger(__name__)


class TelegramError(Exception):
    """Error devuelto por la API de Telegram."""

    def __init__(self, code: int, description: str, retry_after: float | None = None) -> None:
        super().__init__(f"[{code}] {description}")
        self.code = code
        self.description = description
        self.retry_after = retry_after


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Divide un texto largo en trozos que Telegram acepte, cortando por líneas o espacios."""
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = remaining.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


class TelegramApi:
    def __init__(
        self,
        token: str,
        api_base: str = "https://api.telegram.org",
        session: Any | None = None,
        request_timeout: int = 65,
        max_attempts: int = 5,
        sleep=time.sleep,
    ) -> None:
        self._token = token
        self._api_base = api_base.rstrip("/")
        self._session = session or requests.Session()
        self._request_timeout = request_timeout
        self._max_attempts = max_attempts
        self._sleep = sleep

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
        max_attempts: int | None = None,
    ) -> Any:
        url = f"{self._api_base}/bot{self._token}/{method}"
        attempts = max_attempts or self._max_attempts
        timeout = timeout or self._request_timeout
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._session.post(url, json=params or {}, timeout=timeout)
            except requests.RequestException as exc:
                last_error = exc
                if attempt == attempts:
                    break
                delay = min(30.0, 2.0**attempt) * (0.5 + random.random())
                log.warning(
                    "Fallo de red en %s (intento %s/%s): %s. Reintento en %.1fs",
                    method, attempt, attempts, exc, delay,
                )
                self._sleep(delay)
                continue

            try:
                payload = response.json()
            except ValueError:
                payload = {}

            if response.status_code == 200 and payload.get("ok"):
                return payload.get("result")

            description = payload.get("description") or response.text[:200] or f"HTTP {response.status_code}"
            retry_after = (payload.get("parameters") or {}).get("retry_after")
            error = TelegramError(response.status_code, description, retry_after)
            last_error = error

            retryable = response.status_code in RETRYABLE_STATUS or response.status_code >= 500
            if not retryable or attempt == attempts:
                raise error

            delay = float(retry_after) if retry_after else min(30.0, 2.0**attempt)
            log.warning("%s falló (%s). Reintento en %.1fs", method, error, delay)
            self._sleep(delay)

        if isinstance(last_error, TelegramError):
            raise last_error
        raise TelegramError(0, f"no se pudo contactar con Telegram: {last_error}")

    def get_me(self) -> dict[str, Any]:
        return self.call("get_me")

    def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
        limit: int = 100,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": timeout, "limit": limit}
        if offset is not None:
            params["offset"] = offset
        if allowed_updates:
            params["allowed_updates"] = allowed_updates
        return self.call("get_updates", params, timeout=timeout + 15, max_attempts=3) or []

    def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = "HTML",
        reply_to_message_id: int | None = None,
        disable_web_page_preview: bool = True,
    ) -> list[dict[str, Any]]:
        sent: list[dict[str, Any]] = []
        for chunk in split_message(text):
            params: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": disable_web_page_preview,
            }
            if parse_mode:
                params["parse_mode"] = parse_mode
            if reply_to_message_id:
                params["reply_to_message_id"] = reply_to_message_id
            sent.append(self.call("send_message", params))
        return sent
