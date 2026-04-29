"""
grok_client.py — Cliente unificado.
  - Texto (guion, preguntas): Google Gemini 1.5 Flash (gratuito)
  - Imagen (miniaturas):      Google Gemini Imagen (gratuito)
  - Video (clips):            Grok Aurora
"""

import os, time, logging, requests, base64

log = logging.getLogger("grok_client")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROK_BASE   = "https://api.x.ai/v1"

class GrokClient:
    def __init__(self, api_key=None):
        self.grok_key   = api_key or os.environ.get("GROK_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.grok_headers = {
            "Authorization": f"Bearer {self.grok_key}",
            "Content-Type" : "application/json",
        }

    def chat(self, user, system="", model="meta-llama/llama-3.1-8b-instruct:free", max_tokens=2000, temperature=0.8):
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        r = requests.post(url, json=body, headers=headers, timeout=60)
        if not r.ok:
            raise RuntimeError(f"OpenRouter error {r.status_code}: {r.text[:400]}")
        return r.json()["choices"][0]["message"]["content"].strip()
    def generate_image(self, prompt, size="1280x720", model="imagen-3.0-generate-002"):
        url = f"{GEMINI_BASE}/models/{model}:predict?key={self.gemini_key}"
        body = {"instances":[{"prompt":prompt}],"parameters":{"sampleCount":1}}
        r = requests.post(url, json=body, timeout=60)
        if not r.ok:
            log.warning(f"Imagen error {r.status_code}, usando placeholder")
            return self._placeholder(prompt)
        return base64.b64decode(r.json()["predictions"][0]["bytesBase64Encoded"])

    def _placeholder(self, prompt):
        from PIL import Image
        from io import BytesIO
        import hashlib
        h = int(hashlib.md5(prompt.encode()).hexdigest()[:6], 16)
        img = Image.new("RGB", (1280,720), color=((h>>16)&0xFF,(h>>8)&0xFF,h&0xFF))
        buf = BytesIO()
        img.save(buf, "JPEG")
        return buf.getvalue()

    def generate_video_clip(self, prompt, first_frame=None, duration_s=10, model="aurora"):
        body = {"model":model,"prompt":prompt,"duration":duration_s,"response_format":"b64_json"}
        if first_frame:
            body["first_frame"] = base64.b64encode(first_frame).decode()
        r = self._grok_post("/video/generations", body)
        if "job_id" in r:
            return self._poll_video(r["job_id"])
        return base64.b64decode(r["data"][0]["b64_json"])

    def _poll_video(self, job_id, timeout=300):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self._grok_get(f"/video/generations/{job_id}")
            status = r.get("status","pending")
            if status == "completed":
                return base64.b64decode(r["data"][0]["b64_json"])
            if status == "failed":
                raise RuntimeError(f"Grok video failed: {r}")
            time.sleep(15)
        raise TimeoutError("Video job timeout")

    def _grok_post(self, path, body):
        r = requests.post(GROK_BASE+path, json=body, headers=self.grok_headers, timeout=120)
        if not r.ok:
            raise RuntimeError(f"Grok error {r.status_code}: {r.text[:400]}")
        return r.json()

    def _grok_get(self, path):
        r = requests.get(GROK_BASE+path, headers=self.grok_headers, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Grok error {r.status_code}: {r.text[:400]}")
        return r.json()
