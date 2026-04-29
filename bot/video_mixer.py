"""
video_mixer.py — Concatena clips de video y mezcla el audio con FFmpeg.
"""

import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("video_mixer")

TARGET_W   = 1080
TARGET_H   = 1920
TARGET_FPS = 24


class VideoMixer:
    def mix(self, clips: list[Path], audio_path: Path, duration: int = 50) -> Path:
        trimmed    = self._trim_clips(clips)
        concat_path = self._write_concat_list(trimmed)
        joined_path = self._concat_clips(concat_path)
        final_path  = self._mix_audio(joined_path, audio_path, duration)
        log.info(f"Video final: {final_path}")
        return final_path

    def _trim_clips(self, clips: list[Path]) -> list[Path]:
        """Recorta cada clip a 10 segundos y reduce resolución para velocidad."""
        trimmed = []
        for i, clip in enumerate(clips):
            out = Path(tempfile.gettempdir()) / f"trimmed_{i:02d}.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clip),
                "-t", "10",
                "-vf", f"scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={TARGET_FPS}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "32",
                "-pix_fmt", "yuv420p",
                "-an",
                str(out),
            ]
            self._run(cmd, f"trim_{i}")
            trimmed.append(out)
        return trimmed

    def _write_concat_list(self, clips: list[Path]) -> Path:
        list_path = Path(tempfile.gettempdir()) / "concat_list.txt"
        with open(list_path, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")
        return list_path

    def _concat_clips(self, concat_list: Path) -> Path:
        out = Path(tempfile.gettempdir()) / "joined.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-vf", f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={TARGET_FPS}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",
            "-an",
            str(out),
        ]
        self._run(cmd, "concat_clips")
        return out

    def _mix_audio(self, video_path: Path, audio_path: Path, duration: int) -> Path:
        out = Path(tempfile.gettempdir()) / "final_short.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter
