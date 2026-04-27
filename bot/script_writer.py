"""
script_writer.py — Genera el guion completo para un Short de ~50 segundos.
"""

import json
import logging
import re

from grok_client import GrokClient

log = logging.getLogger("script_writer")

SYSTEM_PROMPT = """
Eres un guionista experto en YouTube Shorts virales en español.
Tu tarea es crear un guion de exactamente ~50 segundos (≈120 palabras en narración)
a partir de la instrucción del creador.

REGLAS:
- La narración total debe ser ≈120 palabras (ni más ni menos).
- Divide el video en 5 segmentos visuales de ~10 segundos cada uno.
- Cada segmento tiene un prompt de video para Grok Aurora (en inglés, descriptivo y cinematográfico).
- El tono debe adaptarse a la instrucción (dramático, educativo, divertido, etc.).
- El título debe ser llamativo, máx 80 caracteres, apto para Shorts.
- Los tags deben ser relevantes para YouTube en español.

RESPONDE ÚNICAMENTE con JSON válido, sin markdown, sin explicaciones:
{
  "title": "...",
  "topic": "2-4 palabras del tema",
  "description": "Descripción YouTube max 300 chars. #hashtag1 #hashtag2 #hashtag3",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "narration": "Texto completo ~120 palabras para narración TTS...",
  "segments": [
    {
      "index": 1,
      "duration_s": 10,
      "narration_chunk": "Texto de este segmento...",
      "prompt_video": "Cinematic prompt in English for this segment..."
    }
  ]
}
"""


class ScriptWriter:
    def __init__(self):
        self.client = GrokClient()

    def generate(self, instruccion: str) -> dict:
        log.info(f"Generando guion para: {instruccion[:100]}")
        prompt = self._build_prompt(instruccion)
        raw = self.client.chat(
            system=SYSTEM_PROMPT,
            user=prompt,
            model="gemini-2.0-flash",
            max_tokens=1500,
            temperature=0.85,
        )
        data = self._parse_json(raw)
        self._validate(data)
        log.info(f"Guion generado: '{data['title']}' | {len(data['segments'])} segmentos")
        return data

    def _build_prompt(self, instruccion: str) -> str:
        words = len(instruccion.split())
        if words < 8:
            return (
                f"Instrucción del creador: «{instruccion}»\n\n"
                "La instrucción es breve. Elige el ángulo más interesante y viral "
                "para este tema. Define tú el tono y crea el guion completo."
            )
        else:
            return (
                f"Instrucción detallada del creador:\n{instruccion}\n\n"
                "Respeta todos los detalles, tono y enfoque indicados."
            )

    def _parse_json(self, raw: str) -> dict:
        clean = re.sub(r"```json|```", "", raw).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            log.error(f"JSON inválido:\n{clean[:500]}")
            raise ValueError(f"Gemini no devolvió JSON válido: {e}") from e

    def _validate(self, data: dict):
        required = ["title", "topic", "description", "tags", "narration", "segments"]
        for key in required:
            if key not in data:
                raise ValueError(f"Falta campo '{key}' en el guion")
        if not data["segments"]:
            raise ValueError("El guion no tiene segmentos")
        for seg in data["segments"]:
            seg.setdefault("duration_s", 10)
