"""Tests del bucle del bot: despacho de comandos, estado y reinicio."""

from __future__ import annotations

import json


from bot.api import TelegramApi
from bot.bot import Bot
from bot.commands import REGISTRY
from bot.config import Config


def make_bot(telegram, **overrides) -> Bot:
    options = {
        "token": telegram.token,
        "api_base": telegram.base_url,
        "poll_timeout": 1,
        "drain_on_start": False,
    }
    options.update(overrides)
    config = Config(**options)
    api = TelegramApi(config.token, config.api_base, sleep=lambda _s: None, max_attempts=2)
    return Bot(api, config, sleep=lambda _s: None)


def test_todos_los_comandos_tienen_descripcion():
    assert "clima" in REGISTRY
    assert all(item.description for item in REGISTRY.values())


def test_start_responde_con_bienvenida(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/start", username="ana")
    bot.poll_once()
    textos = telegram.sent_texts()
    assert len(textos) == 1
    assert "ana" in textos[0]


def test_help_lista_los_comandos(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/help")
    bot.poll_once()
    texto = telegram.sent_texts()[0]
    for nombre in REGISTRY:
        assert f"/{nombre}" in texto


def test_help_funciona_con_sufijo_de_usuario(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/help@mi_bot")
    bot.poll_once()
    assert "Comandos disponibles" in telegram.sent_texts()[0]


def test_comando_desconocido(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/noexiste")
    bot.poll_once()
    assert "No conozco el comando" in telegram.sent_texts()[0]


def test_mensaje_sin_comando_se_ignora(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("hola, ¿qué tal?")
    bot.poll_once()
    assert telegram.sent_texts() == []


def test_echo_escapa_html(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/echo <b>hola</b>")
    bot.poll_once()
    assert telegram.sent_texts() == ["&lt;b&gt;hola&lt;/b&gt;"]


def test_echo_sin_argumentos_muestra_uso(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/echo")
    bot.poll_once()
    assert "Uso" in telegram.sent_texts()[0]


def test_dado_devuelve_un_numero_valido(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/dado 20")
    bot.poll_once()
    texto = telegram.sent_texts()[0]
    assert "de 20" in texto
    assert any(str(n) in texto for n in range(1, 21))


def test_estado_responde(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/estado")
    bot.poll_once()
    assert "Estado del bot" in telegram.sent_texts()[0]


def test_lista_blanca_bloquea_usuarios(telegram):
    bot = make_bot(telegram, allowed_user_ids=frozenset({999}))
    telegram.queue_message("/start", user_id=7)
    bot.poll_once()
    assert "No tienes permiso" in telegram.sent_texts()[0]


def test_lista_blanca_permite_usuarios_autorizados(telegram):
    bot = make_bot(telegram, allowed_user_ids=frozenset({7}))
    telegram.queue_message("/start", user_id=7)
    bot.poll_once()
    assert "Hola" in telegram.sent_texts()[0]


def test_offset_avanza_y_no_reprocesa(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/start")
    telegram.queue_message("/help")

    assert bot.poll_once() == 2
    assert len(telegram.sent_texts()) == 2

    assert bot.poll_once() == 0
    assert len(telegram.sent_texts()) == 2
    assert bot.offset == 3


def test_respuesta_cita_el_mensaje_original(telegram):
    bot = make_bot(telegram)
    update_id = telegram.queue_message("/ping")
    bot.poll_once()
    assert telegram.calls_of("sendMessage")[0]["reply_to_message_id"] == update_id * 10


def test_estado_persistente_evita_reprocesar(telegram, tmp_path):
    state_file = tmp_path / "state" / "bot.json"
    primer_bot = make_bot(telegram, state_file=str(state_file))
    telegram.queue_message("/start")
    primer_bot.poll_once()
    assert json.loads(state_file.read_text())["offset"] == 2

    segundo_bot = make_bot(telegram, state_file=str(state_file))
    assert segundo_bot.offset == 2
    assert segundo_bot.poll_once() == 0
    assert len(telegram.sent_texts()) == 1


def test_drain_descarta_mensajes_antiguos(telegram):
    bot = make_bot(telegram, drain_on_start=True)
    telegram.queue_message("/start")
    telegram.queue_message("/help")
    telegram.queue_message("/ping")

    bot.drain_pending()
    assert bot.offset == 4
    assert bot.poll_once() == 0
    assert telegram.sent_texts() == []


def test_run_termina_al_alcanzar_el_tiempo_maximo(telegram):
    reloj = [0.0]

    def clock() -> float:
        reloj[0] += 1.0
        return reloj[0]

    bot = make_bot(telegram, max_runtime_seconds=2)
    bot._started_monotonic = 0.0
    bot._clock = clock
    bot.run()
    assert bot.updates_processed == 0


def test_run_procesa_mensajes_y_se_detiene(telegram):
    telegram.queue_message("/start")

    bot = make_bot(telegram, max_runtime_seconds=0)

    def detener() -> None:
        bot.stop_event.set()

    original = bot.poll_once

    def poll_y_parar(timeout=None):
        resultado = original(timeout)
        detener()
        return resultado

    bot.poll_once = poll_y_parar
    bot.run()
    assert bot.updates_processed == 1
    assert "Hola" in telegram.sent_texts()[0]


def test_trigger_restart_llama_a_la_api_de_github(telegram):
    bot = make_bot(
        telegram,
        self_restart=True,
        github_repository="dueno/repo",
        github_workflow="bot.yml",
        github_ref="main",
        github_token="token-de-prueba",
        github_api_base=telegram.base_url,
    )
    bot.trigger_restart()
    assert telegram.dispatches == [{"ref": "main"}]


def test_error_en_comando_no_rompe_el_bucle(telegram, monkeypatch):
    from bot.commands.registry import REGISTRY as registro

    def explotar(ctx):
        raise RuntimeError("fallo simulado")

    original = registro["ping"].handler
    monkeypatch.setitem(registro, "ping", type(registro["ping"])("ping", "falla", explotar))
    try:
        bot = make_bot(telegram)
        telegram.queue_message("/ping")
        bot.poll_once()
        assert "Ocurrió un error" in telegram.sent_texts()[0]
    finally:
        monkeypatch.setitem(registro, "ping", type(registro["ping"])("ping", "ok", original))


def test_clima_consulta_open_meteo(telegram, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TEST-TOKEN")
    monkeypatch.setenv("TELEGRAM_API_BASE", telegram.base_url)
    monkeypatch.setenv("POLL_TIMEOUT", "1")
    monkeypatch.setenv("DRAIN_ON_START", "false")
    monkeypatch.setenv("WEATHER_GEOCODE_URL", f"{telegram.base_url}/geo")
    monkeypatch.setenv("WEATHER_FORECAST_URL", f"{telegram.base_url}/forecast")

    config = Config.from_env()
    api = TelegramApi(config.token, config.api_base, sleep=lambda _s: None)
    bot = Bot(api, config, sleep=lambda _s: None)

    telegram.queue_message("/clima Madrid")
    bot.poll_once()

    texto = telegram.sent_texts()[0]
    assert "Madrid" in texto
    assert "21.5" in texto
    assert "mayormente despejado" in texto


def test_clima_sin_argumentos_muestra_uso(telegram):
    bot = make_bot(telegram)
    telegram.queue_message("/clima")
    bot.poll_once()
    assert "Uso" in telegram.sent_texts()[0]
