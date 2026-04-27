"""
video_generator.py — Genera los clips de video con Grok Aurora.

Técnica del último fotograma:
  Clip 1: solo prompt → genera video, extrae último frame con FFmpeg
  Clip 2: prompt + primer_frame=último_frame_del_clip_anterior
  Clip N: idem → continuidad visual garantizada
  
Todos los clips se guardan en /tmp/clips/ como archivos .mp4
"""

import os
import logging
import subprocess
import tempfile
from pathlib import Path

from grok_client import GrokClient

log = logging.getLogger("video_generator")

CLIPS_DIR = Path(tempfile.gettempdir()) / "yt_shorts_clips"


class VideoGenerator:
    def __init__(self):
        self.client    = GrokClient()
        self.clips_dir = CLIPS_DIR
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def generate_clips(self, segments: list[dict]) -> list[Path]:
        """
        Genera un clip por segmento usando la técnica del último fotograma.
        Devuelve lista de rutas a los archivos .mp4 en orden.
        """
        clips      : list[Path] = []
        last_frame : bytes | None = None

        for i, seg in enumerate(segments):
            log.info(f"Generando clip {i+1}/{len(segments)}: {seg['prompt_video'][:60]}")
            clip_path = self._generate_clip(
                index       = i + 1,
                prompt      = seg["prompt_video"],
                first_frame = last_frame,
                duration_s  = seg.get("duration_s", 10),
            )
            clips.append(clip_path)
            # Extraer último frame para el siguiente clip
            last_frame = self._extract_last_frame(clip_path)
            log.info(f"Clip {i+1} listo → {clip_path.name} | frame extraído: {len(last_frame)} bytes")

        return clips

    # ─────────────────────────────────────────────────────────────────────────
    def _generate_clip(
        self,
        index      : int,
        prompt     : str,
        first_frame: bytes | None,
        duration_s : int,
    ) -> Path:
        """Llama a Grok Aurora y guarda el clip mp4."""
        video_bytes = self.client.generate_video_clip(
            prompt      = prompt,
            first_frame = first_frame,
            duration_s  = duration_s,
        )
        path = self.clips_dir / f"clip_{index:02d}.mp4"
        path.write_bytes(video_bytes)
        return path

    def _extract_last_frame(self, clip_path: Path) -> bytes:
        """
        Usa FFmpeg para extraer el último fotograma del clip como PNG.
        Comando: ffmpeg -sseof -0.1 -i input.mp4 -frames:v 1 -f image2pipe pipe:1
        """
        cmd = [
            "ffmpeg", "-y",
            "-sseof", "-0.1",          # 0.1 segundos antes del final
            "-i", str(clip_path),
            "-frames:v", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "pipe:1",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            err = result.stderr.decode()[-300:]
            raise RuntimeError(f"FFmpeg error extrayendo frame: {err}")
        return result.stdout
