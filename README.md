# 🤖 Bot de Telegram 24/7

Bot de Telegram escrito en Python que se despliega en **GitHub Actions** y se mantiene
encendido todo el día, sin servidor propio y sin pagar hosting.

- Long polling puro (`getUpdates`): no necesitas dominio, HTTPS ni webhook.
- Auto-reinicio antes de que GitHub corte el job (límite de 6 h) + cron de vigilancia.
- Estado persistente (offset) entre reinicios, para no repetir respuestas.
- Reintentos con backoff ante errores de red, 429 y 5xx.
- Lista blanca opcional de usuarios.
- 32 tests automáticos con un servidor HTTP que imita la API de Telegram.

## Comandos

| Comando | Qué hace |
| --- | --- |
| `/start` | Mensaje de bienvenida |
| `/help` | Lista todos los comandos |
| `/ping` | Comprueba que el bot responde y mide la latencia |
| `/id` | Tu ID de usuario y de chat (útil para la lista blanca) |
| `/echo <texto>` | Repite el texto (con el HTML escapado) |
| `/hora` | Fecha y hora en UTC y del servidor |
| `/clima <ciudad>` | Clima actual vía Open-Meteo (sin clave de API) |
| `/dado [caras]` | Lanza un dado de 6 caras o de las caras que pidas |
| `/moneda` | Cara o cruz |
| `/chiste` | Chiste de programadores |
| `/frase` | Frase motivacional |
| `/estado` | Uptime, actualizaciones procesadas, versión, PID |

## 1. Crear el bot en Telegram

1. Abre Telegram y busca **@BotFather**.
2. Envía `/newbot`.
3. Elige un nombre visible (por ejemplo, `Mi Bot de Allan`) y un usuario que termine en
   `bot` (por ejemplo, `allan_utils_bot`).
4. BotFather te devuelve un token con esta pinta:
   `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`. **Ese token es la contraseña del bot**: no lo
   publiques ni lo subas al repositorio.
5. Opcional pero recomendado: `/setcommands` en BotFather y pega esta lista para que
   Telegram muestre el menú de comandos.

```text
start - Mensaje de bienvenida
help - Lista de comandos
ping - Comprueba que el bot responde
id - Tu ID de usuario y de chat
echo - Repite un texto
hora - Fecha y hora actuales
clima - Clima actual de una ciudad
dado - Lanza un dado
moneda - Cara o cruz
chiste - Chiste de programadores
frase - Frase motivacional
estado - Estado del bot
```

## 2. Desplegar en GitHub

1. Crea un repositorio y sube este código (rama `main`).
2. En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
   - Nombre: `TELEGRAM_BOT_TOKEN`
   - Valor: el token de BotFather.
3. Opcional: en la pestaña **Variables**, crea `ALLOWED_USER_IDS` con tu ID numérico
   (lo consigues con `/id`) si quieres que solo tú puedas usar el bot.
4. Ve a **Actions → Telegram Bot → Run workflow** para arrancarlo la primera vez.
   A partir de ahí se mantiene solo.

Comprueba que funciona enviando `/start` a tu bot en Telegram.

### Cómo se mantiene encendido

```text
cron cada 6 h ──► workflow "Telegram Bot"
                      │
                      ├─ restaura offset (caché)
                      ├─ python -m bot   ── long polling ──► Telegram
                      │        │
                      │        └─ a las 5 h 20 min: pide un workflow_dispatch
                      │           y termina (antes del corte de 6 h)
                      └─ guarda offset (caché)
```

- **Auto-reinicio:** el bot pide una nueva ejecución del workflow con la API de GitHub y
  termina de forma limpia. La ejecución nueva arranca al liberarse el grupo de
  `concurrency`, así que no hay dos instancias a la vez (Telegram devolvería `409`).
- **Cron de vigilancia:** cada 6 h lanza una ejecución por si el auto-reinicio fallara.
- **Estado:** el `offset` de `getUpdates` se guarda en la caché de Actions para no
  responder dos veces al mismo mensaje. Si no hay estado, el bot descarta los mensajes
  pendientes al arrancar (`DRAIN_ON_START`).
- **Keepalive:** GitHub desactiva los workflows programados tras 60 días sin actividad.
  El workflow `Keepalive` hace un commit pequeño el día 1 de cada mes para evitarlo.

### Límites que conviene conocer

- **Repositorio público = minutos gratis.** En un repo privado, Actions da 2.000
  minutos/mes en el plan gratuito, y 24/7 necesita unos 21.900. Con el repo público los
  minutos son ilimitados. El código no contiene secretos: el token vive en los secrets.
- **Hueco de segundos entre ejecuciones.** Al cambiar de ejecución hay unos segundos sin
  bot; los mensajes de ese momento se descartan al arrancar.
- **Los jobs no son instantáneos.** GitHub puede tardar en arrancar una ejecución, sobre
  todo en horas punta.

## 3. Alternativas de despliegue

### Docker

```bash
cp .env.example .env      # y pon tu TELEGRAM_BOT_TOKEN
docker compose up -d --build
docker compose logs -f
```

### Railway / Render / Fly.io

El `Dockerfile` sirve tal cual: crea el servicio desde el repositorio, define la variable
`TELEGRAM_BOT_TOKEN` y deja el comando por defecto (`python -m bot`).

### VPS con systemd

```ini
[Unit]
Description=Telegram bot
After=network-online.target

[Service]
WorkingDirectory=/opt/telegram-bot
EnvironmentFile=/opt/telegram-bot/.env
ExecStart=/opt/telegram-bot/.venv/bin/python -m bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 4. Desarrollo local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # pon tu token

export $(grep -v '^#' .env | xargs)
python -m bot
```

Tests:

```bash
pytest
```

Los tests levantan un servidor HTTP local que imita la API de Telegram y Open-Meteo, así
que no necesitan token real ni red.

## 5. Variables de entorno

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — (obligatoria) | Token de BotFather |
| `ALLOWED_USER_IDS` | vacío (todos) | IDs de usuario permitidos, separados por comas |
| `LOG_LEVEL` | `INFO` | Nivel de log |
| `POLL_TIMEOUT` | `30` | Segundos de long polling |
| `MAX_RUNTIME_SECONDS` | `0` (sin límite) | Apaga el proceso tras N segundos |
| `STATE_FILE` | vacío | Fichero donde guardar el offset |
| `DRAIN_ON_START` | `true` | Descartar mensajes pendientes al arrancar sin estado |
| `SELF_RESTART` | `false` | Pedir un `workflow_dispatch` al terminar |
| `GITHUB_REPOSITORY` | — | `dueno/repo`, lo rellena Actions |
| `GITHUB_WORKFLOW_FILE` | `bot.yml` | Workflow que se reinicia |
| `GITHUB_REF_NAME` | `main` | Rama del reinicio |
| `GH_TOKEN` | — | Token para pedir el reinicio |

## 6. Seguridad

- El token **solo** va en los secrets del repositorio o en tu `.env` local (ignorado por
  git). Nunca en el código.
- Si el token se filtra, habla con @BotFather y usa `/revoke` para generar uno nuevo;
  después actualiza el secret.
- `ALLOWED_USER_IDS` evita que desconocidos usen tu bot.
- Los textos que devuelve el usuario (`/echo`) se escapan antes de enviarlos con
  `parse_mode=HTML`, para que no puedan inyectar etiquetas.

## 7. Estructura

```text
bot/
├── __main__.py        # entrada: python -m bot
├── api.py             # cliente HTTP de Telegram, reintentos, troceado de mensajes
├── bot.py             # bucle de long polling, despacho, estado, auto-reinicio
├── config.py          # variables de entorno
├── context.py         # contexto que recibe cada comando
└── commands/
    ├── registry.py    # decorador @command y ayuda autogenerada
    ├── basic.py       # start, help, ping, id, echo, hora, estado
    ├── fun.py         # dado, moneda, chiste, frase
    └── weather.py     # clima con Open-Meteo
tests/
├── conftest.py        # servidor falso de Telegram y Open-Meteo
├── test_api.py
└── test_bot.py
.github/workflows/
├── bot.yml            # el bot 24/7
├── keepalive.yml      # evita el apagado por inactividad
└── tests.yml          # CI
```

### Añadir un comando

```python
# bot/commands/fun.py
from .registry import command

@command("saludo", "Saluda por tu nombre")
def saludo(ctx):
    return f"¡Hola, {ctx.username}!"
```

Se registra solo y aparece en `/help`.

## Licencia

MIT.
