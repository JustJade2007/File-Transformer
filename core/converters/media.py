"""Media converter supporting audio, video, audio extraction, and GIF generation via FFmpeg."""
import os
import re
import sys
import time
import subprocess
from typing import Callable, Dict, List, Optional, Set

from .base import BaseConverter, ConversionResult
from ..ffmpeg_manager import FFmpegManager

AUDIO_FORMATS = {"mp3", "wav", "flac", "aac", "ogg", "oga", "m4a", "wma", "aiff"}
VIDEO_FORMATS = {"mp4", "mkv", "mov", "webm", "avi", "wmv", "flv", "m4v"}
ALL_MEDIA_INPUTS = AUDIO_FORMATS | VIDEO_FORMATS | {"mid", "midi"}


class MediaConverter(BaseConverter):
    """Handles audio and video transcoding, extraction, and generation."""

    name = "Audio/Video Engine (FFmpeg)"
    category = "Media"

    def __init__(self):
        self.manager = FFmpegManager()

    def supported_inputs(self) -> Set[str]:
        return ALL_MEDIA_INPUTS

    def supported_outputs(self, input_ext: Optional[str] = None) -> Set[str]:
        if not input_ext:
            return AUDIO_FORMATS | VIDEO_FORMATS | {"gif"}
        clean = input_ext.lower().lstrip(".")
        if clean in VIDEO_FORMATS:
            # Video can convert to other video formats, audio formats (extract), or gif
            return VIDEO_FORMATS | AUDIO_FORMATS | {"gif"}
        if clean in AUDIO_FORMATS or clean in {"mid", "midi"}:
            # Audio can convert to other audio formats, or to mp4/webm video container
            return AUDIO_FORMATS | {"mp4", "webm"}
        return set()

    def get_default_options(self, source_ext: str, target_ext: str) -> Dict:
        clean_target = target_ext.lower().lstrip(".")
        if clean_target in VIDEO_FORMATS:
            return {
                "video_resolution": "Original",
                "video_quality": "High (CRF 20)",
                "fps": "Original",
                "audio_bitrate": "192k",
            }
        elif clean_target in AUDIO_FORMATS:
            return {
                "audio_bitrate": "256k",
                "sample_rate": "Original",
            }
        elif clean_target == "gif":
            return {
                "gif_fps": 15,
                "gif_width": 480,
            }
        return {}

    def _get_media_duration(self, file_path: str) -> Optional[float]:
        """Use ffprobe to query exact duration in seconds."""
        ffprobe = self.manager.get_ffprobe_path()
        if not ffprobe:
            return None
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            cmd = [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creationflags, timeout=10)
            if res.returncode == 0:
                return float(res.stdout.strip())
        except Exception:
            pass
        return None

    def convert(
        self,
        source_path: str,
        target_path: str,
        target_format: str,
        options: Optional[Dict] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[object] = None,
    ) -> ConversionResult:
        start_time = time.time()
        ffmpeg = self.manager.get_ffmpeg_path()
        if not ffmpeg or not self.manager.is_available():
            return ConversionResult(
                success=False,
                error_message="FFmpeg is not available. Please install FFmpeg or use the in-app 1-click downloader in Settings.",
            )

        source_ext = os.path.splitext(source_path)[1].lower().lstrip(".")
        target_ext = target_format.lower().lstrip(".")
        opts = options or self.get_default_options(source_ext, target_ext)

        # Make sure parent directory of output exists
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

        # Probe duration for progress tracking
        total_duration = self._get_media_duration(source_path)

        # Build ffmpeg command line
        cmd = [ffmpeg, "-y", "-i", source_path]

        # Handle specific conversion targets
        if target_ext == "gif":
            fps = opts.get("gif_fps", 15)
            width = opts.get("gif_width", 480)
            # Two-pass palettegen + paletteuse filter for crisp, high-quality GIFs
            vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd.extend(["-vf", vf, target_path])

        elif target_ext in AUDIO_FORMATS:
            cmd.extend(["-vn"])  # disable video stream
            audio_bitrate = opts.get("audio_bitrate", "256k")
            if target_ext == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", audio_bitrate])
            elif target_ext == "flac":
                cmd.extend(["-c:a", "flac"])
            elif target_ext == "wav":
                cmd.extend(["-c:a", "pcm_s16le"])
            elif target_ext in ("aac", "m4a"):
                cmd.extend(["-c:a", "aac", "-b:a", audio_bitrate])
            elif target_ext in ("ogg", "oga"):
                cmd.extend(["-c:a", "libvorbis", "-q:a", "6"])
            elif target_ext == "wma":
                cmd.extend(["-c:a", "wmav2", "-b:a", audio_bitrate])
            elif target_ext == "aiff":
                cmd.extend(["-c:a", "pcm_s16be"])
            cmd.append(target_path)

        elif target_ext in VIDEO_FORMATS and source_ext in AUDIO_FORMATS:
            # Audio to video with generated color background visual
            cmd = [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", "color=c=0x1e1e2e:s=1280x720:r=25",
                "-i", source_path,
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                target_path,
            ]

        else:
            # Video to Video
            resolution = opts.get("video_resolution", "Original")
            if resolution == "1080p":
                cmd.extend(["-vf", "scale=-2:1080"])
            elif resolution == "720p":
                cmd.extend(["-vf", "scale=-2:720"])
            elif resolution == "480p":
                cmd.extend(["-vf", "scale=-2:480"])

            fps = opts.get("fps", "Original")
            if fps not in ("Original", "", None):
                cmd.extend(["-r", str(fps)])

            quality = str(opts.get("video_quality", "High (CRF 20)"))
            crf = "20"
            if "CRF 18" in quality or "Ultra" in quality:
                crf = "18"
            elif "CRF 23" in quality or "Medium" in quality:
                crf = "23"
            elif "CRF 28" in quality or "Low" in quality:
                crf = "28"

            if target_ext == "webm":
                cmd.extend(["-c:v", "libvpx-vp9", "-crf", crf, "-b:v", "0", "-c:a", "libopus"])
            elif target_ext == "avi":
                cmd.extend(["-c:v", "mpeg4", "-qscale:v", "3", "-c:a", "libmp3lame"])
            elif target_ext == "wmv":
                cmd.extend(["-c:v", "wmv2", "-c:a", "wmav2"])
            else:
                # Default high quality H.264 + AAC
                cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-c:a", "aac", "-b:a", "192k"])

            cmd.append(target_path)

        # Execute conversion process
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                bufsize=1,
                universal_newlines=True,
            )

            # Monitor stderr for progress
            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            last_progress = 0.0

            while process.poll() is None:
                if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                    process.kill()
                    if os.path.exists(target_path):
                        try:
                            os.remove(target_path)
                        except Exception:
                            pass
                    return ConversionResult(
                        success=False,
                        error_message="Conversion was cancelled.",
                        duration_seconds=time.time() - start_time,
                    )

                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                match = time_pattern.search(line)
                if match and total_duration and total_duration > 0:
                    hours = float(match.group(1))
                    mins = float(match.group(2))
                    secs = float(match.group(3))
                    cur_secs = hours * 3600 + mins * 60 + secs
                    frac = min(0.99, cur_secs / total_duration)
                    if frac - last_progress >= 0.02:
                        last_progress = frac
                        if progress_callback:
                            progress_callback(frac, f"Transcoding... {int(frac * 100)}%")

                time.sleep(0.02)

            return_code = process.wait()
            duration = time.time() - start_time

            if return_code == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                if progress_callback:
                    progress_callback(1.0, "Complete")
                return ConversionResult(
                    success=True,
                    output_path=target_path,
                    duration_seconds=duration,
                )
            else:
                stderr_output = process.stderr.read()
                return ConversionResult(
                    success=False,
                    error_message=f"FFmpeg error: {stderr_output[-300:] if stderr_output else 'Unknown failure'}",
                    duration_seconds=duration,
                )

        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Execution failed: {str(e)}",
                duration_seconds=time.time() - start_time,
            )
