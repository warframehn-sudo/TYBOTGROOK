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
TARGET_FPS = 30


class VideoMixer:
    def mix(self, clips: list[Path], audio_path: Path, duration: int = 50) -> Path:
        concat_path = self._write_concat_list(clips)
        joined_path = self._concat_clips(concat_path)
        final_path  = self._mix_audio(joined_path, audio_path, duration)
        log.info(f"Video final: {final_path}")
        return final_path

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
            "-max_muxing_queue_size", "9999",
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
            "-filter_complex",
            f"[0:v]trim=0:{duration},setpts=PTS-STARTPTS[v];[1:a]atrim=0:{duration},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out),
        ]
        self._run(cmd, "mix_audio")
        return out

    def _run(self, cmd: list[str], step: str):
        log.info(f"FFmpeg [{step}]: {' '.join(cmd[:6])}...")
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode()[-500:]
            raise RuntimeError(f"FFmpeg [{step}] falló:\n{err}")
