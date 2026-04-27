"""
uploader.py — Sube el Short a YouTube con la YouTube Data API v3.
Usa OAuth2 con refresh_token (sin necesidad de login interactivo en CI).

Setup inicial (una sola vez, en tu máquina local):
  Ver README.md → sección "Configurar YouTube OAuth2"
"""

import json
import logging
import os
import tempfile
from pathlib import Path

import requests

log = logging.getLogger("uploader")

TOKEN_URL     = "https://oauth2.googleapis.com/token"
UPLOAD_URL    = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMB_URL     = "https://www.googleapis.com/youtube/v3/thumbnails/set"
STATE_FILE    = "config/last_video.json"


class YouTubeUploader:
    def __init__(self):
        self.client_id     = os.environ["YOUTUBE_CLIENT_ID"]
        self.client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
        self.refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]
        self._access_token : str | None = None

    def upload(
        self,
        video_path : Path,
        thumb_path : Path,
        title      : str,
        description: str,
        tags       : list[str],
    ) -> str:
        """Sube video + miniatura. Devuelve la URL del Short."""
        token    = self._get_access_token()
        video_id = self._upload_video(token, video_path, title, description, tags)
        self._set_thumbnail(token, video_id, thumb_path)
        url = f"https://youtube.com/shorts/{video_id}"
        self._save_state(title, url)
        log.info(f"Short publicado: {url}")
        return url

    # ─────────────────────────────────────────────────────────────────────────
    def _get_access_token(self) -> str:
        r = requests.post(TOKEN_URL, data={
            "client_id"    : self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type"   : "refresh_token",
        }, timeout=15)
        r.raise_for_status()
        return r.json()["access_token"]

    def _upload_video(
        self,
        token      : str,
        video_path : Path,
        title      : str,
        description: str,
        tags       : list[str],
    ) -> str:
        """Resumable upload a YouTube. Devuelve el video_id."""
        metadata = {
            "snippet": {
                "title"      : title[:100],
                "description": description[:5000],
                "tags"       : tags[:30],
                "categoryId" : "22",       # People & Blogs (ajusta si prefieres otra)
            },
            "status": {
                "privacyStatus"       : "public",
                "selfDeclaredMadeForKids": False,
            },
        }
        headers = {
            "Authorization"   : f"Bearer {token}",
            "Content-Type"    : "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        }
        # 1. Iniciar sesión de upload resumable
        init_r = requests.post(
            UPLOAD_URL + "?uploadType=resumable&part=snippet,status",
            headers = headers,
            json    = metadata,
            timeout = 30,
        )
        init_r.raise_for_status()
        upload_uri = init_r.headers["Location"]

        # 2. Subir el archivo
        with open(video_path, "rb") as f:
            up_r = requests.put(
                upload_uri,
                headers = {"Authorization": f"Bearer {token}"},
                data    = f,
                timeout = 600,
            )
        up_r.raise_for_status()
        video_id = up_r.json()["id"]
        log.info(f"Video subido: {video_id}")
        return video_id

    def _set_thumbnail(self, token: str, video_id: str, thumb_path: Path):
        with open(thumb_path, "rb") as f:
            r = requests.post(
                THUMB_URL + f"?videoId={video_id}",
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                data    = f,
                timeout = 60,
            )
        if not r.ok:
            log.warning(f"No se pudo subir miniatura: {r.text[:200]}")

    def _save_state(self, title: str, url: str):
        from datetime import datetime, timezone
        data = {
            "title"       : title,
            "url"         : url,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "duration"    : 50,
        }
        os.makedirs("config", exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
