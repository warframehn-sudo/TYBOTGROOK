"""
telegram_bot.py
───────────────
Panel de control principal del bot de YouTube Shorts.
Comandos disponibles:
  /video [tema extendido o corto]  → genera y sube un Short
  /ask   [pregunta sobre el canal] → responde con Grok
  /status                          → estado del bot y último video
  /cancel                          → cancela una generación en curso
"""

import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from pipeline import run_pipeline
from instruction_parser import parse_instruction

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s · %(name)s · %(levelname)s · %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
OWNER_CHAT_ID    = int(os.environ["OWNER_CHAT_ID"])   # solo tú controlas el bot
GROK_API_KEY     = os.environ["GROK_API_KEY"]

# Estado global ligero (para un solo usuario)
bot_state = {
    "running": False,
    "current_task": None,
    "last_video_url": None,
    "last_topic": None,
}

# ── Guardián: solo el dueño puede usar el bot ─────────────────────────────────
def owner_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != OWNER_CHAT_ID:
            await update.message.reply_text("⛔ Bot privado.")
            return
        return await func(update, ctx)
    return wrapper

# ── /start ────────────────────────────────────────────────────────────────────
@owner_only
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎬 *Bot de YouTube Shorts activo*\n\n"
        "Comandos disponibles:\n"
        "• `/video [tema]` — genera y sube un Short de 50 seg\n"
        "• `/ask [pregunta]` — consulta sobre tu canal o ideas\n"
        "• `/status` — estado del bot y último video subido\n"
        "• `/cancel` — cancela la generación en curso\n\n"
        "Puedes darme el tema de forma *corta* o muy *detallada*, yo me adapto."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── /video ────────────────────────────────────────────────────────────────────
@owner_only
async def cmd_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if bot_state["running"]:
        await update.message.reply_text(
            "⏳ Ya hay una generación en curso.\n"
            "Usa /cancel para detenerla o espera a que termine."
        )
        return

    # Captura todo el texto después de /video
    raw = " ".join(ctx.args) if ctx.args else ""
    if not raw:
        await update.message.reply_text(
            "📝 Dime el tema del video.\n"
            "Ejemplo:\n"
            "`/video Los 3 errores que cometen los principiantes en Python`\n\n"
            "O con más detalle:\n"
            "`/video Quiero un video sobre Python para principiantes, enfocado en errores comunes "
            "de listas y bucles, con ejemplos divertidos y tono juvenil`",
            parse_mode="Markdown"
        )
        return

    # Parsear si la instrucción es corta o extensa
    plan = parse_instruction(raw)

    # Confirmación visual antes de arrancar
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Generar", callback_data=f"confirm_video"),
            InlineKeyboardButton("✏️ Editar", callback_data="cancel_video"),
        ]
    ])
    ctx.user_data["pending_plan"] = plan
    ctx.user_data["pending_raw"]  = raw

    summary = (
        f"*Plan detectado:*\n"
        f"📌 Tema: {plan['topic']}\n"
        f"🎯 Ángulos: {', '.join(plan['angles'])}\n"
        f"🗣️ Tono: {plan['tone']}\n"
        f"⏱️ Duración objetivo: {plan['duration']}s\n"
        f"📊 Segmentos Grok: ~{plan['segments']}\n\n"
        f"¿Arrancamos?"
    )
    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=kb)

# ── Callback de confirmación ──────────────────────────────────────────────────
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_video":
        await query.edit_message_text("❌ Cancelado. Vuelve a escribir /video con el tema que quieras.")
        return

    if query.data == "confirm_video":
        plan = ctx.user_data.get("pending_plan")
        if not plan:
            await query.edit_message_text("❌ No hay plan pendiente. Usa /video [tema].")
            return

        bot_state["running"] = True
        bot_state["last_topic"] = plan["topic"]
        await query.edit_message_text(
            f"🚀 *Generando Short...*\n\n"
            f"Te iré informando del progreso.\n"
            f"Tema: _{plan['topic']}_",
            parse_mode="Markdown"
        )

        # Ejecutar pipeline en background sin bloquear Telegram
        chat_id = query.message.chat_id
        bot_state["current_task"] = asyncio.create_task(
            run_pipeline_and_notify(plan, chat_id, ctx.application.bot)
        )

# ── Pipeline async con notificaciones de progreso ─────────────────────────────
async def run_pipeline_and_notify(plan: dict, chat_id: int, bot):
    steps = [
        ("✍️ Escribiendo guion...",          "script"),
        ("🖼️ Generando miniatura...",        "thumbnail"),
        ("🎬 Generando video con Grok...",   "video"),
        ("🔊 Generando audio...",            "audio"),
        ("🎞️ Mezclando video + audio...",    "mix"),
        ("📤 Subiendo a YouTube...",         "upload"),
    ]

    progress_msg = await bot.send_message(chat_id, "⏳ Iniciando pipeline...")

    try:
        for label, step_key in steps:
            await progress_msg.edit_text(label)
            result = await asyncio.to_thread(run_pipeline, plan, step_key)

            if not result["ok"]:
                raise RuntimeError(f"Fallo en {step_key}: {result['error']}")

        # Éxito
        video_url = result.get("youtube_url", "URL no disponible")
        bot_state["last_video_url"] = video_url

        await progress_msg.edit_text(
            f"✅ *Short publicado exitosamente*\n\n"
            f"🎬 [{plan['topic']}]({video_url})\n\n"
            f"Usa /status para ver el resumen.",
            parse_mode="Markdown",
            disable_web_page_preview=False
        )

    except Exception as e:
        log.error(f"Pipeline error: {e}")
        await progress_msg.edit_text(
            f"❌ *Error en la generación*\n\n`{str(e)}`\n\nRevisa los logs en GitHub Actions.",
            parse_mode="Markdown"
        )
    finally:
        bot_state["running"] = False
        bot_state["current_task"] = None

# ── /ask ──────────────────────────────────────────────────────────────────────
@owner_only
async def cmd_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    question = " ".join(ctx.args) if ctx.args else ""
    if not question:
        await update.message.reply_text(
            "❓ Escribe tu pregunta después de /ask\n"
            "Ejemplo: `/ask Qué temas funcionan mejor para mi canal de Python?`",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text("🤔 Consultando a Grok...")

    # Llamada a Grok para responder preguntas sobre el canal
    from grok_client import ask_grok
    answer = await asyncio.to_thread(ask_grok, question, context="canal_youtube")
    await update.message.reply_text(f"🤖 *Grok dice:*\n\n{answer}", parse_mode="Markdown")

# ── /status ───────────────────────────────────────────────────────────────────
@owner_only
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    estado = "🟡 Generando video..." if bot_state["running"] else "🟢 Listo"
    ultimo = bot_state["last_video_url"] or "Ninguno aún"
    tema   = bot_state["last_topic"] or "—"

    msg = (
        f"*Estado del bot*\n\n"
        f"• Estado: {estado}\n"
        f"• Último tema: _{tema}_\n"
        f"• Último video: {ultimo}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── /cancel ───────────────────────────────────────────────────────────────────
@owner_only
async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if bot_state["current_task"] and not bot_state["current_task"].done():
        bot_state["current_task"].cancel()
        bot_state["running"] = False
        await update.message.reply_text("🛑 Generación cancelada.")
    else:
        await update.message.reply_text("ℹ️ No hay ninguna generación en curso.")

# ── Mensajes libres (sin comando) ─────────────────────────────────────────────
@owner_only
async def free_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Si escribes sin comando, el bot pregunta qué quieres hacer."""
    text = update.message.text or ""
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Hacer video", callback_data=f"free_video"),
            InlineKeyboardButton("❓ Preguntar",   callback_data="free_ask"),
        ]
    ])
    ctx.user_data["free_text"] = text
    await update.message.reply_text(
        f"Recibido: _\"{text[:80]}{'...' if len(text)>80 else ''}\"_\n\n¿Qué hago con esto?",
        parse_mode="Markdown",
        reply_markup=kb
    )

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("video",  cmd_video))
    app.add_handler(CommandHandler("ask",    cmd_ask))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_message))

    log.info("Bot arrancado en modo polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
