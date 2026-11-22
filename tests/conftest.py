"""Servidor HTTP local que imita la API de Telegram y Open-Meteo.

Los tests hablan HTTP real contra él, así que ejercitan el mismo camino de código
que en producción (requests, reintentos, parseo de respuestas).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest


class FakeTelegram:
    def __init__(self, token: str = "TEST-TOKEN") -> None:
        self.token = token
        self.updates: list[dict] = []
        self.calls: list[dict] = []
        self.sent: list[dict] = []
        self.http_calls: list[tuple[str, dict]] = []
        self.dispatches: list[dict] = []
        self.failures: list[int] = []
        self.next_update_id = 1
        self.lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._make_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "FakeTelegram":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    # --- utilidades para los tests -----------------------------------------

    def queue_message(
        self,
        text: str,
        chat_id: int = 100,
        user_id: int = 7,
        username: str = "tester",
    ) -> int:
        with self.lock:
            update_id = self.next_update_id
            self.next_update_id += 1
            self.updates.append(
                {
                    "update_id": update_id,
                    "message": {
                        "message_id": update_id * 10,
                        "date": 0,
                        "text": text,
                        "chat": {"id": chat_id, "type": "private"},
                        "from": {
                            "id": user_id,
                            "is_bot": False,
                            "first_name": "Test",
                            "username": username,
                        },
                    },
                }
            )
            return update_id

    def queue_update(self, update: dict) -> int:
        with self.lock:
            payload = dict(update)
            payload["update_id"] = self.next_update_id
            self.next_update_id += 1
            self.updates.append(payload)
            return payload["update_id"]

    def sent_texts(self) -> list[str]:
        with self.lock:
            return [params.get("text", "") for params in self.sent]

    def calls_of(self, method: str) -> list[dict]:
        with self.lock:
            return [c["params"] for c in self.calls if c["method"] == method]

    # --- servidor ----------------------------------------------------------

    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # silencia el log de http.server
                pass

            def do_POST(self):
                server._dispatch(self)

            def do_GET(self):
                server._dispatch(self)

            def _read_params(self) -> dict:
                parsed = urlparse(self.path)
                params: dict = {}
                for key, values in parse_qs(parsed.query).items():
                    params[key] = values[-1]
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    raw = self.rfile.read(length)
                    try:
                        body = json.loads(raw or b"{}")
                    except ValueError:
                        body = {}
                    if isinstance(body, dict):
                        params.update(body)
                return params

            def _respond(self, status: int, payload) -> None:
                body = b"" if status == 204 else json.dumps(payload).encode()
                self.send_response(status)
                if status != 204:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

        return Handler

    def _dispatch(self, handler) -> None:
        params = handler._read_params()
        path = urlparse(handler.path).path
        status, payload = self.handle_path(path, params)
        handler._respond(status, payload)

    def handle_path(self, path: str, params: dict) -> tuple[int, dict | None]:
        if path.startswith(f"/bot{self.token}/"):
            return self.handle_telegram(path.rsplit("/", 1)[-1], params)

        with self.lock:
            self.http_calls.append((path, params))

        if path.startswith("/geo"):
            return 200, {
                "results": [
                    {
                        "name": "Madrid",
                        "country": "España",
                        "latitude": 40.4168,
                        "longitude": -3.7038,
                    }
                ]
            }
        if path.startswith("/forecast"):
            return 200, {
                "current": {
                    "temperature_2m": 21.5,
                    "relative_humidity_2m": 55,
                    "apparent_temperature": 21.0,
                    "wind_speed_10m": 8.4,
                    "weather_code": 1,
                }
            }
        if "/dispatches" in path:
            self.dispatches.append(params)
            return 204, None
        return 404, {"ok": False, "description": f"ruta desconocida {path}"}

    def handle_telegram(self, method: str, params: dict) -> tuple[int, dict | None]:
        with self.lock:
            self.calls.append({"method": method, "params": params})
            if self.failures:
                status = self.failures.pop(0)
                return status, {
                    "ok": False,
                    "description": f"fallo simulado {status}",
                    "parameters": {"retry_after": 0},
                }

        if method == "get_me":
            return 200, {
                "ok": True,
                "result": {"id": 1, "is_bot": True, "first_name": "Test", "username": "test_bot"},
            }
        if method == "get_updates":
            return self._get_updates(params)
        if method == "send_message":
            return self._send_message(params)
        return 404, {"ok": False, "description": f"método desconocido: {method}"}

    def _get_updates(self, params: dict) -> tuple[int, dict]:
        raw_offset = params.get("offset")
        offset = int(raw_offset) if raw_offset not in (None, "") else None
        limit = int(params.get("limit") or 100)
        with self.lock:
            if offset is not None and offset < 0:
                return 200, {"ok": True, "result": self.updates[-1:]}
            if offset is None:
                pending = list(self.updates)
            else:
                pending = [u for u in self.updates if u["update_id"] >= offset]
        return 200, {"ok": True, "result": pending[:limit]}

    def _send_message(self, params: dict) -> tuple[int, dict]:
        if "chat_id" not in params or "text" not in params:
            return 400, {"ok": False, "description": "chat_id y text son obligatorios"}
        if len(params["text"]) > 4096:
            return 400, {"ok": False, "description": "message is too long"}
        with self.lock:
            self.sent.append(params)
        return 200, {
            "ok": True,
            "result": {
                "message_id": 5000 + len(self.calls),
                "text": params["text"],
                "chat": {"id": params["chat_id"]},
            },
        }


@pytest.fixture
def telegram():
    server = FakeTelegram().start()
    yield server
    server.stop()
