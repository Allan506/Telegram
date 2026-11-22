"""Punto de entrada: `python -m bot`."""

from __future__ import annotations

import logging
import sys

from .api import TelegramApi
from .bot import Bot
from .config import Config


def main() -> int:
    try:
        config = Config.from_env()
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    api = TelegramApi(config.token, config.api_base)
    Bot(api, config).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
