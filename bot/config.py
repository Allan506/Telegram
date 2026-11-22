"""Configuración del bot a partir de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
DEFAULT_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _as_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "si", "sí", "on"}


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} debe ser un número entero (recibido: {raw!r})") from exc


def _as_id_set(name: str) -> frozenset[int]:
    raw = os.getenv(name, "")
    ids: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError as exc:
            raise SystemExit(f"{name} contiene un ID inválido: {chunk!r}") from exc
    return frozenset(ids)


@dataclass(frozen=True)
class Config:
    token: str
    api_base: str = "https://api.telegram.org"
    allowed_user_ids: frozenset[int] = field(default_factory=frozenset)
    log_level: str = "INFO"
    poll_timeout: int = 30
    max_runtime_seconds: int = 0
    state_file: str = ""
    drain_on_start: bool = True
    self_restart: bool = False
    github_repository: str = ""
    github_workflow: str = "bot.yml"
    github_ref: str = "main"
    github_token: str = ""
    github_api_base: str = "https://api.github.com"
    weather_geocode_url: str = DEFAULT_GEOCODE_URL
    weather_forecast_url: str = DEFAULT_FORECAST_URL

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit(
                "Falta TELEGRAM_BOT_TOKEN. Crea un bot con @BotFather en Telegram "
                "y define el token antes de arrancar."
            )

        config = cls(
            token=token,
            api_base=os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/"),
            allowed_user_ids=_as_id_set("ALLOWED_USER_IDS"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            poll_timeout=max(1, _as_int("POLL_TIMEOUT", 30)),
            max_runtime_seconds=max(0, _as_int("MAX_RUNTIME_SECONDS", 0)),
            state_file=os.getenv("STATE_FILE", "").strip(),
            drain_on_start=_as_bool("DRAIN_ON_START", True),
            self_restart=_as_bool("SELF_RESTART", False),
            github_repository=os.getenv("GITHUB_REPOSITORY", "").strip(),
            github_workflow=os.getenv("GITHUB_WORKFLOW_FILE", "bot.yml").strip(),
            github_ref=os.getenv("GITHUB_REF_NAME", "main").strip() or "main",
            github_token=os.getenv("GH_TOKEN", "").strip(),
            github_api_base=os.getenv("GITHUB_API_BASE", "https://api.github.com").rstrip("/"),
            weather_geocode_url=os.getenv("WEATHER_GEOCODE_URL", DEFAULT_GEOCODE_URL),
            weather_forecast_url=os.getenv("WEATHER_FORECAST_URL", DEFAULT_FORECAST_URL),
        )
        if config.self_restart and not (config.github_repository and config.github_token):
            raise SystemExit(
                "SELF_RESTART=true requiere GITHUB_REPOSITORY y GH_TOKEN "
                "(en GitHub Actions se rellenan solos)."
            )
        return config
