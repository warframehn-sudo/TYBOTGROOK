"""
video_generator.py — Descarga clips de video de Pexels según el tema
y los encadena con FFmpeg para hacer un video de 50 segundos.
"""

import os
import logging
import subprocess
import tempfile
import requests
from pathlib import Path

log = logging.getLogger("video_generator")
CLIPS_DIR = Path(tempfile.gettempdir()) / "yt_shorts_clips"
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")


class VideoGenerator:
    def __init__(self):
        self.clips_dir = CLIPS_DIR
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def generate_clips(self, segments: list[dict]) -> list[Path]:
        clips = []
        for i, seg in enumerate(segments):
            log.info(f"Descargando clip {i+1}/{len(segments)}: {seg['prompt_video'][:60]}")
            clip_path = self._download_clip(i + 1, seg["prompt_video"])
            clips.append(clip_path)
        return clips

    def _download_clip(self, index: int, prompt: str) -> Path:
        # Extraer palabras clave del prompt para buscar en Pexels
        keywords = " ".join(prompt.split()[:4])
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_KEY}
        params = {
            "query": keywords,
            "per_page": 3,
            "orientation": "portrait",
            "size": "medium",
        }
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Pexels error {r.status_code}: {r.text[:200]}")

        videos = r.json().get("videos", [])
        if not videos:
            # Si no hay resultados con esas palabras, buscar algo genérico
            params["query"] = "nature cinematic"
            r = requests.get(url, headers=headers, params=params, timeout=30)
            videos = r.json().get("videos", [])

        # Tomar el primer video y buscar el archivo HD
        video = videos[0]
        video_url = None
        for vf in video["video_files"]:
            if vf.get("quality") in ("hd", "sd") and vf.get("width", 0) <= 1080:
                video_url = vf["link"]
                break
        if not video_url:
            video_url = video["video_files"][0]["link"]

        # Descargar el clip
        out_path = self.clips_dir / f"clip_{index:02d}.mp4"
        with requests.get(video_url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

        log.info(f"Clip {index} descargado: {out_path.name}")
        return out_path
