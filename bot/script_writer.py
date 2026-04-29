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
Crea un guion de ~50 segundos a partir de la instrucción del creador.

RESPONDE ÚNICAMENTE con JSON válido, sin markdown, sin texto extra, sin explicaciones.
El JSON debe tener exactamente esta estructura:
{
  "title": "Título llamativo máx 80 chars",
  "topic": "2-4 palabras del tema",
  "description": "Descripción YouTube max 300 chars #hashtag1 #hashtag2",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "narration": "Texto completo de narración de aproximadamente 120 palabras para leer en voz alta durante 50 segundos",
  "segments": [
    {
      "index": 1,
      "duration_s": 10,
      "narration_chunk": "Texto del segmento 1",
      "prompt_video": "Cinematic video prompt in English for segment 1"
    },
    {
      "index": 2,
      "duration_s": 10,
      "narration_chunk": "Texto del segmento 2",
      "prompt_video": "Cinematic video prompt in English for segment 2"
    },
    {
      "index": 3,
      "duration_s": 10,
      "narration_chunk": "Texto del segmento 3",
      "prompt_video": "Cinematic video prompt in English for segment 3"
    },
    {
      "index": 4,
      "duration_s": 10,
      "narration_chunk": "Texto del segmento 4",
      "prompt_video": "Cinematic video prompt in English for segment 4"
    },
    {
      "index": 5,
      "duration_s": 10,
      "narration_chunk": "Texto del segmento 5",
      "prompt_video": "Cinematic video prompt in English for segment 5"
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
            model="meta-llama/llama-3.1-8b-instruct",
            max_tokens=2000,
            temperature=0.7,
        )
        data = self._parse_json(raw)
        data = self._fix_missing_fields(data)
        self._validate(data)
        log.info(f"Guion generado: '{data['title']}' | {len(data['segments'])} segmentos")
        return data

    def _build_prompt(self, instruccion: str) -> str:
        words = len(instruccion.split())
        if words < 8:
            return (
                f"Crea un guion de YouTube Shorts sobre: «{instruccion}»\n"
                "Elige el ángulo más interesante y viral. "
                "Responde SOLO con el JSON, nada más."
            )
        else:
            return (
                f"Crea un guion de YouTube Shorts siguiendo esta instrucción:\n{instruccion}\n"
                "Respeta el tono y enfoque indicados. "
                "Responde SOLO con el JSON, nada más."
            )

    def _parse_json(self, raw: str) -> dict:
        # Limpiar markdown si viene
        clean = re.sub(r"```json|```", "", raw).strip()
        # Intentar extraer JSON con regex si hay texto extra
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            clean = match.group(0)
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            log.error(f"JSON inválido:\n{clean[:500]}")
            raise ValueError(f"No se obtuvo JSON válido: {e}") from e

    def _fix_missing_fields(self, data: dict) -> dict:
        # Si falta narration, construirla uniendo los chunks de segmentos
        if "narration" not in data and "segments" in data:
            chunks = [s.get("narration_chunk", "") for s in data["segments"]]
            data["narration"] = " ".join(chunks)

        # Si falta topic, extraerlo del title
        if "topic" not in data and "title" in data:
            data["topic"] = " ".join(data["title"].split()[:3])

        # Si falta description, usar title
        if "description" not in data:
            data["description"] = data.get("title", "Video de YouTube Shorts")

        # Si faltan tags, poner genéricos
        if "tags" not in data:
            data["tags"] = ["shorts", "viral", "curiosidades"]

        # Asegurar duration_s en cada segmento
        for seg in data.get("segments", []):
            seg.setdefault("duration_s", 10)
            seg.setdefault("prompt_video", "cinematic nature footage")
            seg.setdefault("narration_chunk", "")

        return data

    def _validate(self, data: dict):
        required = ["title", "topic", "description", "tags", "narration", "segments"]
        for key in required:
            if key not in data:
                raise ValueError(f"Falta campo '{key}' en el guion")
        if not data["segments"]:
            raise ValueError("El guion no tiene segmentos")
