"""
main.py — Orquestador principal del YouTube Shorts Bot
Lee el comando enviado desde Telegram y ejecuta el pipeline correspondiente.
"""

import os
import sys
import logging
import traceback

from telegram_notifier import TelegramNotifier
from dispatcher import dispatch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("main")


def main():
    command = os.environ.get("BOT_COMMAND", "").strip().lower()
    payload  = os.environ.get("BOT_PAYLOAD",  "").strip()
    chat_id  = os.environ.get("BOT_CHAT_ID",  os.environ.get("TELEGRAM_CHAT_ID", ""))

    notifier = TelegramNotifier(
        token   = os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id = chat_id,
    )

    if not command:
        log.warning("No se recibió comando. Saliendo.")
        notifier.send("⚠️ Bot ejecutado sin comando.")
        return

    log.info(f"Comando recibido: /{command}  |  payload: {payload[:120]}")
    notifier.send(f"⚙️ Comando recibido: <b>/{command}</b>\nIniciando proceso…")

    try:
        dispatch(command, payload, notifier)
    except Exception:
        err = traceback.format_exc()
        log.error(err)
        notifier.send(f"❌ Error en el pipeline:\n<pre>{err[-800:]}</pre>")
        sys.exit(1)


if __name__ == "__main__":
    main()
