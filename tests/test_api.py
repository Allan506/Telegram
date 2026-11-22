"""Tests del cliente de la API de Telegram."""

from __future__ import annotations

import pytest

from bot.api import TelegramApi, TelegramError, split_message


def make_api(telegram, **kwargs) -> TelegramApi:
    return TelegramApi(
        token=telegram.token,
        api_base=telegram.base_url,
        sleep=lambda _seconds: None,
        max_attempts=kwargs.pop("max_attempts", 3),
        **kwargs,
    )


def test_split_message_no_cambia_textos_cortos():
    assert split_message("hola") == ["hola"]


def test_split_message_corta_por_lineas():
    texto = "\n".join(f"linea {i}" for i in range(500))
    trozos = split_message(texto, limit=200)
    assert len(trozos) > 1
    assert all(len(trozo) <= 200 for trozo in trozos)
    assert "".join(trozos).replace("\n", "") == texto.replace("\n", "")


def test_split_message_corta_texto_sin_espacios():
    trozos = split_message("x" * 250, limit=100)
    assert [len(t) for t in trozos] == [100, 100, 50]


def test_get_me(telegram):
    api = make_api(telegram)
    assert api.get_me()["username"] == "test_bot"


def test_send_message_envia_un_mensaje(telegram):
    api = make_api(telegram)
    api.send_message(100, "hola")
    assert telegram.sent_texts() == ["hola"]
    params = telegram.calls_of("sendMessage")[0]
    assert params["chat_id"] == 100
    assert params["parse_mode"] == "HTML"


def test_send_message_parte_mensajes_largos(telegram):
    api = make_api(telegram)
    api.send_message(100, "a" * 9000)
    assert len(telegram.calls_of("sendMessage")) == 3


def test_reintenta_cuando_telegram_devuelve_429(telegram):
    telegram.failures = [429]
    api = make_api(telegram)
    api.send_message(100, "hola")
    assert len(telegram.calls_of("sendMessage")) == 2
    assert telegram.sent_texts() == ["hola"]


def test_no_reintenta_errores_400(telegram):
    api = make_api(telegram)
    with pytest.raises(TelegramError) as excinfo:
        api.call("metodo_inexistente")
    assert excinfo.value.code == 404
    assert len(telegram.calls_of("metodo_inexistente")) == 1


def test_get_updates_respeta_offset(telegram):
    telegram.queue_message("/start")
    telegram.queue_message("/help")
    api = make_api(telegram)

    primera = api.get_updates(offset=None, timeout=1)
    assert [u["update_id"] for u in primera] == [1, 2]

    segunda = api.get_updates(offset=2, timeout=1)
    assert [u["update_id"] for u in segunda] == [2]

    tercera = api.get_updates(offset=3, timeout=1)
    assert tercera == []


def test_get_updates_con_offset_negativo_devuelve_el_ultimo(telegram):
    telegram.queue_message("/start")
    telegram.queue_message("/help")
    api = make_api(telegram)
    ultimo = api.get_updates(offset=-1, timeout=0, limit=1)
    assert [u["update_id"] for u in ultimo] == [2]


def test_usa_los_nombres_de_metodo_reales_de_telegram(telegram):
    """La API real usa camelCase; el servidor falso devuelve 404 con otros nombres."""
    api = make_api(telegram)
    api.get_me()
    api.get_updates(timeout=1)
    api.send_message(100, "hola")
    assert [call["method"] for call in telegram.calls] == ["getMe", "getUpdates", "sendMessage"]
