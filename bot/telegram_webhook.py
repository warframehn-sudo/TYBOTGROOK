"""
telegram_webhook.py — Servidor webhook de Telegram.

Despliega este script en un servicio gratuito (Railway, Render, Fly.io, etc.)
o en un VPS. Recibe los mensajes de Telegram, los parsea y dispara el
workflow de GitHub Actions via repository_dispatch.

VARIABLES DE ENTORNO NECESARIAS:
  TELEGRAM_BOT_TOKEN   → token del bot de BotFather
  TELEGRAM_SECRET      → string secreto para verificar el webhook
  GITHUB_TOKEN         → Personal Access Token con permiso "repo"
  GITHUB_OWNER         → tu usuario de GitHub
  GITHUB_REPO          → nombre del repositorio
  ALLOWED_CHAT_ID      → tu chat_id de Telegram (solo tú controlas el bot)
"""

import os
import logging
import hashlib
import hmac

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

log = logging.getLogger("webhook")
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_SECRET  = os.environ.get("TELEGRAM_SECRET", "")
GITHUB_TOKEN     = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER     = os.environ["GITHUB_OWNER"]
GITHUB_REPO      = os.environ["GITHUB_REPO"]
ALLOWED_CHAT_ID  = str(os.environ["ALLOWED_CHAT_ID"])   # solo el dueño del canal

DISPATCH_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Comandos válidos y sus alias
VALID_COMMANDS = {"video", "pregunta", "estado", "ayuda", "help", "start"}


# ── Webhook endpoint ──────────────────────────────────────────────────────────
@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Verificar secret header (Telegram lo envía cuando configuras el webhook con secret_token)
    if TELEGRAM_SECRET:
        sig = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if sig != TELEGRAM_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret")

    update = await request.json()
    log.info(f"Update recibido: {str(update)[:200]}")

    # Solo procesar mensajes de texto
    message = update.get("message") or update.get("edited_message")
    if not message or "text" not in message:
        return JSONResponse({"ok": True})

    chat_id = str(message["chat"]["id"])
    text    = message["text"].strip()

    # Seguridad: solo el dueño puede usar el bot
    if chat_id != ALLOWED_CHAT_ID:
        _send_message(chat_id, "⛔ No tienes permiso para usar este bot.")
        return JSONResponse({"ok": True})

    # Parsear comando
    command, payload = _parse_command(text)

    if command not in VALID_COMMANDS:
        _send_message(
            chat_id,
            f"❓ Comando <b>/{command}</b> no reconocido.\nEscribe /ayuda para ver los comandos.",
        )
        return JSONResponse({"ok": True})

    # Confirmación inmediata (GitHub Actions puede tardar en arrancar)
    _send_message(chat_id, f"✅ Comando <b>/{command}</b> recibido. Disparando pipeline…")

    # Disparar GitHub Actions
    success = _dispatch_github(command, payload, chat_id)
    if not success:
        _send_message(chat_id, "❌ Error al disparar GitHub Actions. Revisa los logs.")

    return JSONResponse({"ok": True})


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse_command(text: str) -> tuple[str, str]:
    """
    Parsea mensajes tipo '/video tema aquí' o '/pregunta consulta'.
    Devuelve (comando, payload).
    """
    if not text.startswith("/"):
        # Mensaje sin slash → tomar como comando /video
        return "video", text

    parts   = text.lstrip("/").split(None, 1)
    command = parts[0].lower().split("@")[0]  # quitar @bot_name si viene
    payload = parts[1] if len(parts) > 1 else ""
    return command, payload


def _send_message(chat_id: str, text: str):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json = {
                "chat_id"   : chat_id,
                "text"      : text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout = 10,
        )
    except Exception as e:
        log.error(f"Error enviando mensaje Telegram: {e}")


def _dispatch_github(command: str, payload: str, chat_id: str) -> bool:
    """Dispara el workflow de GitHub Actions con repository_dispatch."""
    body = {
        "event_type"    : "telegram_command",
        "client_payload": {
            "command": command,
            "payload": payload,
            "chat_id": chat_id,
        },
    }
    r = requests.post(
        DISPATCH_URL,
        json    = body,
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept"       : "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout = 15,
    )
    if r.status_code == 204:
        log.info("GitHub Actions disparado correctamente")
        return True
    log.error(f"GitHub dispatch error {r.status_code}: {r.text[:300]}")
    return False
