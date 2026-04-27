"""
grok_client.py — Cliente unificado para la API de Grok (x.ai).

Endpoints usados:
  - /v1/chat/completions  → texto (guion, preguntas, análisis)
  - /v1/images/generations → imagen (miniaturas, primer frame)
  - /v1/video/generations  → video (clips Grok Aurora)  [cuando esté disponible en free tier]
"""

import os
import time
import logging
import requests

log = logging.getLogger("grok_client")

GROK_BASE = "https://api.x.ai/v1"


class GrokClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["GROK_API_KEY"]
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type" : "application/json",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # CHAT / TEXTO
    # ─────────────────────────────────────────────────────────────────────────
    def chat(
        self,
        user      : str,
        system    : str = "",
        model     : str = "grok-3",
        max_tokens: int = 2000,
        temperature: float = 0.8,
    ) -> str:
        """Llamada simple texto → texto. Devuelve el contenido del primer mensaje."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        body = {
            "model"      : model,
            "messages"   : messages,
            "max_tokens" : max_tokens,
            "temperature": temperature,
        }
        r = self._post("/chat/completions", body)
        return r["choices"][0]["message"]["content"].strip()

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGEN (miniaturas / primer fotograma)
    # ─────────────────────────────────────────────────────────────────────────
    def generate_image(
        self,
        prompt : str,
        size   : str = "1080x1920",   # vertical para Shorts
        model  : str = "aurora",
    ) -> bytes:
        """Genera una imagen y devuelve los bytes PNG/JPEG."""
        body = {
            "model"  : model,
            "prompt" : prompt,
            "n"      : 1,
            "size"   : size,
            "response_format": "b64_json",
        }
        r    = self._post("/images/generations", body)
        b64  = r["data"][0]["b64_json"]
        import base64
        return base64.b64decode(b64)

    # ─────────────────────────────────────────────────────────────────────────
    # VIDEO (Grok Aurora — generación con último fotograma)
    # ─────────────────────────────────────────────────────────────────────────
    def generate_video_clip(
        self,
        prompt      : str,
        first_frame : bytes | None = None,   # PNG/JPEG bytes del frame anterior
        duration_s  : int  = 10,
        model       : str  = "aurora",
    ) -> bytes:
        """
        Genera un clip de video.
        Si se provee first_frame, Grok lo usa como fotograma inicial
        para mantener continuidad visual entre clips.
        Devuelve bytes del video (mp4).
        """
        import base64

        body: dict = {
            "model"   : model,
            "prompt"  : prompt,
            "duration": duration_s,
            "response_format": "b64_json",
        }
        if first_frame is not None:
            body["first_frame"] = base64.b64encode(first_frame).decode()

        # La generación de video puede tardar → polling
        r = self._post("/video/generations", body)

        # Si la API devuelve job_id, hacer polling
        if "job_id" in r:
            return self._poll_video(r["job_id"])

        # Respuesta directa con b64
        return base64.b64decode(r["data"][0]["b64_json"])

    def _poll_video(self, job_id: str, timeout: int = 300) -> bytes:
        """Espera hasta que el job de video esté listo."""
        import base64
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self._get(f"/video/generations/{job_id}")
            status = r.get("status", "pending")
            if status == "completed":
                return base64.b64decode(r["data"][0]["b64_json"])
            if status == "failed":
                raise RuntimeError(f"Grok video job failed: {r}")
            log.info(f"Video job {job_id} → {status}. Esperando 15s…")
            time.sleep(15)
        raise TimeoutError(f"Video job {job_id} no terminó en {timeout}s")

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _post(self, path: str, body: dict) -> dict:
        url = GROK_BASE + path
        r   = requests.post(url, json=body, headers=self.headers, timeout=120)
        if not r.ok:
            raise RuntimeError(f"Grok API error {r.status_code}: {r.text[:400]}")
        return r.json()

    def _get(self, path: str) -> dict:
        url = GROK_BASE + path
        r   = requests.get(url, headers=self.headers, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Grok API error {r.status_code}: {r.text[:400]}")
        return r.json()
