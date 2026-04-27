"""
thumbnail_maker.py — Genera la miniatura del Short con Pillow (sin APIs externas).

Estrategia:
  1. Pide a Grok una imagen de fondo relacionada con el tema.
  2. Superpone el título con fuente grande, sombra y color temático.
  3. Guarda como JPG 1280×720 (estándar YouTube thumbnail).
"""

import logging
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO

from grok_client import GrokClient

log = logging.getLogger("thumbnail_maker")

THUMB_W, THUMB_H = 1280, 720
FONT_SIZE_TITLE  = 90
FONT_SIZE_SUB    = 48


class ThumbnailMaker:
    def __init__(self):
        self.client = GrokClient()

    def create(self, title: str, topic: str) -> Path:
        """Genera la miniatura y devuelve la ruta al JPG."""
        log.info(f"Generando miniatura para: {title}")

        # 1. Imagen de fondo desde Grok Aurora (formato 16:9 → 1280x720)
        bg_bytes = self.client.generate_image(
            prompt = (
                f"Cinematic, high-quality background image representing: {topic}. "
                "No text. Dramatic lighting, vibrant colors, 16:9 landscape format."
            ),
            size  = "1280x720",
        )
        bg = Image.open(BytesIO(bg_bytes)).convert("RGB").resize((THUMB_W, THUMB_H))

        # 2. Oscurecer el fondo para que el texto resalte
        overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 140))
        bg = bg.convert("RGBA")
        bg.paste(overlay, (0, 0), overlay)
        bg = bg.convert("RGB")

        draw = ImageDraw.Draw(bg)

        # 3. Cargar fuente (usa la que tenga el sistema; fallback a default)
        title_font = self._load_font(FONT_SIZE_TITLE)
        sub_font   = self._load_font(FONT_SIZE_SUB)

        # 4. Dibujar título centrado con wrap automático
        self._draw_text_wrapped(draw, title, THUMB_W // 2, 300, title_font, max_width=1100)

        # 5. Guardar
        out_path = Path(tempfile.gettempdir()) / "yt_shorts_thumbnail.jpg"
        bg.save(str(out_path), "JPEG", quality=95)
        log.info(f"Miniatura guardada: {out_path}")
        return out_path

    # ─────────────────────────────────────────────────────────────────────────
    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _draw_text_wrapped(
        self,
        draw     : ImageDraw.ImageDraw,
        text     : str,
        cx       : int,
        cy       : int,
        font     : ImageFont.FreeTypeFont,
        max_width: int,
        fill     : tuple = (255, 255, 255),
        shadow   : tuple = (0, 0, 0),
    ):
        """Dibuja texto centrado con salto de línea automático y sombra."""
        words  = text.split()
        lines  = []
        line   = ""
        for word in words:
            test = (line + " " + word).strip()
            w    = draw.textlength(test, font=font)
            if w > max_width and line:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)

        total_h = sum(font.size + 8 for _ in lines)
        y = cy - total_h // 2

        for line_text in lines:
            w = draw.textlength(line_text, font=font)
            x = cx - w // 2
            # Sombra
            draw.text((x + 3, y + 3), line_text, font=font, fill=shadow)
            # Texto principal
            draw.text((x, y), line_text, font=font, fill=fill)
            y += font.size + 8
