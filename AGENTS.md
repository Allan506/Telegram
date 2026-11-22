# AGENTS.md

Bot de Telegram en Python (long polling) desplegado 24/7 en GitHub Actions.

## Comandos

```bash
pip install -r requirements-dev.txt
pytest                                  # 32 tests, sin red ni token real
python -m bot                           # requiere TELEGRAM_BOT_TOKEN
ruff check bot tests --select F,E9      # lint
```

## Arquitectura

- `bot/api.py`: cliente de la API de Telegram. Único punto que habla HTTP con Telegram.
  Reintenta 429 y 5xx con backoff; trocea mensajes de más de 4000 caracteres.
- `bot/bot.py`: bucle de long polling, despacho, offset persistente, auto-reinicio.
- `bot/commands/`: cada comando se registra con `@command(nombre, descripción, uso)` y
  devuelve el texto a enviar (o `None`). `/help` se genera solo desde el registro.
- `bot/config.py`: toda la configuración sale de variables de entorno, con `Config.from_env()`.

## Convenciones

- Los textos que vienen del usuario se escapan con `html.escape` antes de enviarlos:
  los mensajes se envían con `parse_mode=HTML`.
- Los tests usan un servidor HTTP real (`tests/conftest.py`) que imita Telegram y
  Open-Meteo. No se usan mocks: se apunta `TELEGRAM_API_BASE` y las URLs del clima al
  servidor local.
- Un comando nuevo va en el módulo temático que corresponda de `bot/commands/` y se
  prueba en `tests/test_bot.py`.

## Despliegue

`.github/workflows/bot.yml` ejecuta `python -m bot` con `MAX_RUNTIME_SECONDS=19200`
(5 h 20 min) y `SELF_RESTART=true`, para pedir un `workflow_dispatch` antes del corte de
6 h de GitHub. Un cron cada 6 h actúa de vigilancia. El offset se conserva en la caché
de Actions (`state/bot-state.json`).
