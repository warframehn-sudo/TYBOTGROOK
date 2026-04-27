"""
telegram_notifier.py — Envía mensajes HTML a un chat de Telegram.
Usado por todos los módulos para informar el progreso al dueño del canal.
"""

import logging
import requests

log = logging.getLogger("telegram")


class TelegramNotifier:
    BASE = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = chat_id

    def send(self, text: str, disable_preview: bool = True) -> bool:
        """Envía un mensaje HTML al chat configurado."""
        url = self.BASE.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id"                  : self.chat_id,
            "text"                     : text,
            "parse_mode"               : "HTML",
            "disable_web_page_preview" : disable_preview,
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Telegram send error: {e}")
            return False

    def send_document(self, file_path: str, caption: str = "") -> bool:
        """Envía un archivo (ej. el video final) al chat."""
        url = self.BASE.format(token=self.token, method="sendDocument")
        try:
            with open(file_path, "rb") as f:
                r = requests.post(
                    url,
                    data    = {"chat_id": self.chat_id, "caption": caption, "parse_mode": "HTML"},
                    files   = {"document": f},
                    timeout = 120,
                )
            r.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Telegram send_document error: {e}")
            return False
