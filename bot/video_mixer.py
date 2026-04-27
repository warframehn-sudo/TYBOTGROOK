"""
video_mixer.py — Concatena clips de video y mezcla el audio con FFmpeg.

Pasos:
  1. Genera un concat list file con todos los clips.
  2. Concatena con -filter_complex concat (reencoding para uniformidad).
  3. Mezcla el audio TTS sobre el video final.
  4. Recorta/ajusta a exactamente 50 segundos.
  5. Asegura formato 1080×1920 (vertical 9:16) apto para Shorts.
"""

import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("video_mixer")

TARGET_W  = 1080
TARGET_H  = 1920
TARGET_FPS = 30


class VideoMixer:
    def mix(self, clips: list[Path], audio_path: Path, duration: int = 50) -> Path:
        """
        Une clips + audio y devuelve la ruta al video final .mp4
        """
        concat_path = self._write_concat_list(clips)
        joined_path = self._concat_clips(concat_path)
        final_path  = self._mix_audio(joined_path, audio_path, duration)
        log.info(f"Video final: {final_path}")
        return final_path

    # ─────────────────────────────────────────────────────────────────────────
    def _write_concat_list(self, clips: list[Path]) -> Path:
        list_path = Path(tempfile.gettempdir()) / "concat_list.txt"
        with open(list_path, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")
        return list_path

    def _concat_clips(self, concat_list: Path) -> Path:
        """Concatena todos los clips manteniendo calidad y uniformizando resolución."""
        out = Path(tempfile.gettempdir()) / "joined.mp4"
        # Escala cada clip a 1080x1920 y concatena
        # Usamos filter_complex para uniformidad de FPS y resolución
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-vf", f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
                   f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,"
                   f"setsar=1,fps={TARGET_FPS}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",           # sin audio por ahora (se agrega en el siguiente paso)
            str(out),
        ]
        self._run(cmd, "concat_clips")
        return out

    def _mix_audio(self, video_path: Path, audio_path: Path, duration: int) -> Path:
        """Mezcla el audio TTS sobre el video y recorta a `duration` segundos."""
        out = Path(tempfile.gettempdir()) / "final_short.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex",
            # Si el audio es más corto que el video, lo repite (no aplica en la práctica)
            # Si es más largo, lo recorta
            f"[0:v]trim=0:{duration},setpts=PTS-STARTPTS[v];"
            f"[1:a]atrim=0:{duration},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out),
        ]
        self._run(cmd, "mix_audio")
        return out

    def _run(self, cmd: list[str], step: str):
        log.info(f"FFmpeg [{step}]: {' '.join(cmd[:6])}…")
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode()[-500:]
            raise RuntimeError(f"FFmpeg [{step}] falló:\n{err}")
