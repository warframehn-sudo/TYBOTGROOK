"""
audio_generator.py — Genera la narración de voz usando Edge TTS (gratis, sin límite).
Edge TTS usa las voces neurales de Microsoft sin necesidad de API key.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

import edge_tts

log = logging.getLogger("audio_generator")

# Voces en español disponibles en Edge TTS (todas gratuitas):
#   es-MX-DaliaNeural     — femenina, México, clara y natural
#   es-ES-AlvaroNeural    — masculina, España
#   es-AR-TomasNeural     — masculino, Argentina
#   es-CO-GonzaloNeural   — masculino, Colombia
DEFAULT_VOICE = "es-MX-DaliaNeural"


class AudioGenerator:
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice

    def generate(self, text: str) -> Path:
        """Genera audio MP3 a partir del texto de narración. Devuelve la ruta al archivo."""
        out_path = Path(tempfile.gettempdir()) / "yt_shorts_narration.mp3"
        asyncio.run(self._synthesize(text, out_path))
        log.info(f"Audio generado: {out_path} ({out_path.stat().st_size // 1024} KB)")
        return out_path

    async def _synthesize(self, text: str, out_path: Path):
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(str(out_path))
