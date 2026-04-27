"""
dispatcher.py — Enruta el comando de Telegram al pipeline correcto.

Comandos soportados:
  /video  [tema / instrucción larga o corta]  → pipeline completo de Short
  /pregunta [consulta sobre canal/videos]     → respuesta de Grok por Telegram
  /estado                                     → info del último video publicado
  /ayuda                                      → lista de comandos
"""

import logging
from telegram_notifier import TelegramNotifier

log = logging.getLogger("dispatcher")


def dispatch(command: str, payload: str, notifier: TelegramNotifier):
    match command:
        case "video":
            _pipeline_video(payload, notifier)
        case "pregunta":
            _pipeline_pregunta(payload, notifier)
        case "estado":
            _pipeline_estado(notifier)
        case "ayuda" | "help" | "start":
            _pipeline_ayuda(notifier)
        case _:
            notifier.send(
                f"❓ Comando <b>/{command}</b> no reconocido.\n"
                "Escribe /ayuda para ver los comandos disponibles."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline: /video
# ─────────────────────────────────────────────────────────────────────────────
def _pipeline_video(instruccion: str, notifier: TelegramNotifier):
    """
    Ejecuta el pipeline completo:
    instrucción → guion → miniatura → video Grok → audio → mezcla → YouTube
    """
    if not instruccion:
        notifier.send("❌ Debes dar un tema o instrucción.\nEj: /video Curiosidades del espacio profundo")
        return

    from script_writer    import ScriptWriter
    from thumbnail_maker  import ThumbnailMaker
    from video_generator  import VideoGenerator
    from audio_generator  import AudioGenerator
    from video_mixer      import VideoMixer
    from uploader         import YouTubeUploader

    # 1. Analizar instrucción y generar guion
    notifier.send("📝 Generando guion…")
    writer = ScriptWriter()
    script_data = writer.generate(instruccion)          # dict con titulo, guion, segmentos, tags

    notifier.send(
        f"✅ Guion listo: <b>{script_data['title']}</b>\n"
        f"Segmentos: {len(script_data['segments'])} | Duración objetivo: ~50 seg"
    )

    # 2. Miniatura
    notifier.send("🖼 Generando miniatura…")
    thumb_path = ThumbnailMaker().create(script_data["title"], script_data["topic"])

    # 3. Video (cadena de fotogramas en Grok)
    notifier.send("🎬 Generando clips de video con Grok (puede tardar 3-5 min)…")
    clips = VideoGenerator().generate_clips(script_data["segments"])

    # 4. Audio (narración TTS)
    notifier.send("🎙 Generando narración…")
    audio_path = AudioGenerator().generate(script_data["narration"])

    # 5. Mezcla final con FFmpeg
    notifier.send("🔧 Mezclando video + audio…")
    final_video = VideoMixer().mix(clips, audio_path, duration=50)

    # 6. Subir a YouTube
    notifier.send("🚀 Subiendo Short a YouTube…")
    video_url = YouTubeUploader().upload(
        video_path   = final_video,
        thumb_path   = thumb_path,
        title        = script_data["title"],
        description  = script_data["description"],
        tags         = script_data["tags"],
    )

    notifier.send(
        f"🎉 <b>¡Short publicado!</b>\n"
        f"📹 <b>{script_data['title']}</b>\n"
        f"🔗 {video_url}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline: /pregunta
# ─────────────────────────────────────────────────────────────────────────────
def _pipeline_pregunta(consulta: str, notifier: TelegramNotifier):
    """Responde preguntas sobre el canal usando Grok como LLM."""
    if not consulta:
        notifier.send("❌ Escribe tu pregunta después del comando.\nEj: /pregunta ¿Qué temas funcionan mejor en mi canal?")
        return

    from grok_client import GrokClient
    import json, os

    # Contexto del canal (se puede enriquecer con datos reales de YouTube Analytics)
    canal_info = _load_channel_context()

    client = GrokClient()
    respuesta = client.chat(
        system  = (
            "Eres el asistente de gestión de un canal de YouTube Shorts. "
            "Conoces el contexto del canal y ayudas al creador a tomar decisiones "
            "sobre contenido, temas, publicación y crecimiento. "
            "Responde en español, de forma concisa y útil. "
            f"Contexto del canal:\n{canal_info}"
        ),
        user    = consulta,
    )

    notifier.send(f"🤖 <b>Respuesta:</b>\n{respuesta}")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline: /estado
# ─────────────────────────────────────────────────────────────────────────────
def _pipeline_estado(notifier: TelegramNotifier):
    """Muestra el estado del último video generado."""
    import json, os
    state_file = "config/last_video.json"
    if not os.path.exists(state_file):
        notifier.send("ℹ️ Aún no se ha generado ningún video en este repositorio.")
        return
    with open(state_file) as f:
        data = json.load(f)
    notifier.send(
        f"📊 <b>Último video:</b>\n"
        f"• Título: {data.get('title','N/A')}\n"
        f"• Publicado: {data.get('published_at','N/A')}\n"
        f"• URL: {data.get('url','N/A')}\n"
        f"• Duración: {data.get('duration','N/A')} seg"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline: /ayuda
# ─────────────────────────────────────────────────────────────────────────────
def _pipeline_ayuda(notifier: TelegramNotifier):
    notifier.send(
        "🤖 <b>YouTube Shorts Bot — Comandos</b>\n\n"
        "/video [tema o instrucción]\n"
        "  Genera y publica un Short de ~50 seg.\n"
        "  Puedes ser breve: <i>/video curiosidades del sol</i>\n"
        "  O extenso: <i>/video quiero un video sobre los agujeros negros, "
        "enfocado en qué pasaría si la Tierra cayera en uno, tono dramático</i>\n\n"
        "/pregunta [consulta]\n"
        "  Pregunta sobre tu canal, ideas de contenido, estrategia, etc.\n\n"
        "/estado\n"
        "  Muestra info del último Short publicado.\n\n"
        "/ayuda\n"
        "  Muestra este mensaje."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────
def _load_channel_context() -> str:
    """Carga el contexto del canal desde config/channel_context.txt si existe."""
    import os
    path = "config/channel_context.txt"
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return "Canal de YouTube Shorts en español. Contenido educativo y de entretenimiento."
