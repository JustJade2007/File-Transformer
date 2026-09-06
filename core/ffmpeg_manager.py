"""FFmpeg detection, management, and portable static binary downloader."""
import os
import sys
import shutil
import subprocess
import threading
import urllib.request
import zipfile
from typing import Callable, Optional, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_BIN_DIR = os.path.join(APP_DIR, "bin")

# Reliable static release builds for Windows
FFMPEG_WINDOWS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
# Fallback GitHub release mirror
FFMPEG_MIRROR_URL = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"


class FFmpegManager:
    """Manages system detection, version checks, and portable download of FFmpeg."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FFmpegManager, cls).__new__(cls)
                cls._instance._custom_path = None
                cls._instance._cached_info = None
            return cls._instance

    def set_custom_path(self, path: Optional[str]):
        """Set a user-specified directory containing ffmpeg.exe and ffprobe.exe."""
        self._custom_path = path
        self._cached_info = None

    def get_bin_dir(self) -> str:
        """Return the local portable bin directory."""
        os.makedirs(LOCAL_BIN_DIR, exist_ok=True)
        return LOCAL_BIN_DIR

    def get_ffmpeg_path(self) -> Optional[str]:
        """Locate ffmpeg executable in custom dir, local bin, or system PATH."""
        # 1. Custom directory
        if self._custom_path:
            custom_exe = os.path.join(self._custom_path, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            if os.path.isfile(custom_exe) and os.access(custom_exe, os.X_OK):
                return custom_exe

        # 2. Local app bin directory
        local_exe = os.path.join(LOCAL_BIN_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if os.path.isfile(local_exe):
            return local_exe

        # 3. System PATH
        which_path = shutil.which("ffmpeg")
        if which_path:
            return which_path

        return None

    def get_ffprobe_path(self) -> Optional[str]:
        """Locate ffprobe executable in custom dir, local bin, or system PATH."""
        if self._custom_path:
            custom_exe = os.path.join(self._custom_path, "ffprobe.exe" if os.name == "nt" else "ffprobe")
            if os.path.isfile(custom_exe) and os.access(custom_exe, os.X_OK):
                return custom_exe

        local_exe = os.path.join(LOCAL_BIN_DIR, "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.isfile(local_exe):
            return local_exe

        which_path = shutil.which("ffprobe")
        if which_path:
            return which_path

        return None

    def is_available(self) -> bool:
        """Check if a working ffmpeg binary is accessible."""
        path = self.get_ffmpeg_path()
        if not path:
            return False
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
            res = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    def get_version_info(self) -> Tuple[bool, str, str]:
        """
        Return (is_available, version_string, binary_path).
        """
        path = self.get_ffmpeg_path()
        if not path:
            return False, "Not Found", ""

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
            res = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                timeout=5,
            )
            if res.returncode == 0:
                first_line = res.stdout.splitlines()[0] if res.stdout else "Unknown version"
                return True, first_line, path
            return False, "Execution Error", path
        except Exception as e:
            return False, str(e), path

    def download_portable_ffmpeg(
        self,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """
        Download and extract a portable FFmpeg static release directly to bin/.
        """
        bin_dir = self.get_bin_dir()
        temp_zip = os.path.join(bin_dir, "ffmpeg_download.zip")

        urls_to_try = [FFMPEG_WINDOWS_URL, FFMPEG_MIRROR_URL]
        download_success = False
        error_details = ""

        for url in urls_to_try:
            if cancel_event and cancel_event.is_set():
                return False, "Download cancelled."

            try:
                if progress_callback:
                    progress_callback(0.05, f"Connecting to {url.split('/')[2]}...")

                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FileTransformer/1.0"}
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    total_size = int(response.info().get("Content-Length", 0))
                    downloaded = 0
                    block_size = 1024 * 64  # 64 KB chunks

                    with open(temp_zip, "wb") as out_file:
                        while True:
                            if cancel_event and cancel_event.is_set():
                                out_file.close()
                                if os.path.exists(temp_zip):
                                    os.remove(temp_zip)
                                return False, "Download cancelled."

                            chunk = response.read(block_size)
                            if not chunk:
                                break
                            out_file.write(chunk)
                            downloaded += len(chunk)

                            if progress_callback and total_size > 0:
                                frac = 0.05 + 0.70 * (downloaded / total_size)
                                mb_down = downloaded / (1024 * 1024)
                                mb_tot = total_size / (1024 * 1024)
                                progress_callback(frac, f"Downloading: {mb_down:.1f} MB / {mb_tot:.1f} MB")

                download_success = True
                break
            except Exception as e:
                error_details = str(e)
                if os.path.exists(temp_zip):
                    try:
                        os.remove(temp_zip)
                    except Exception:
                        pass
                continue

        if not download_success:
            return False, f"Failed to download FFmpeg: {error_details}"

        # Extract ffmpeg.exe and ffprobe.exe
        try:
            if progress_callback:
                progress_callback(0.80, "Extracting binaries from archive...")

            with zipfile.ZipFile(temp_zip, "r") as zf:
                target_names = ["ffmpeg.exe", "ffprobe.exe"]
                extracted_count = 0
                for member in zf.namelist():
                    basename = os.path.basename(member).lower()
                    if basename in target_names:
                        dest_path = os.path.join(bin_dir, basename)
                        with zf.open(member) as source_f, open(dest_path, "wb") as target_f:
                            shutil.copyfileobj(source_f, target_f)
                        extracted_count += 1

            if os.path.exists(temp_zip):
                os.remove(temp_zip)

            if extracted_count > 0:
                if progress_callback:
                    progress_callback(1.0, "FFmpeg installed successfully.")
                self._cached_info = None
                return True, f"FFmpeg installed successfully in {bin_dir}."
            else:
                return False, "Archive did not contain ffmpeg.exe or ffprobe.exe."
        except Exception as e:
            return False, f"Extraction failed: {str(e)}"
