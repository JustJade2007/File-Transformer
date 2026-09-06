"""Archive and package converter for ZIP, TAR, GZ, BZ2, APK, DEB, and extract workflows."""
import bz2
import gzip
import os
import shutil
import tarfile
import tempfile
import time
from typing import Callable, Dict, List, Optional, Set
import zipfile

from .base import BaseConverter, ConversionResult

ARCHIVE_INPUTS = {"zip", "tar", "gz", "bz2", "apk", "jar", "deb"}
ARCHIVE_OUTPUTS = {"zip", "tar", "tar.gz", "tar.bz2", "gz", "bz2"}


class ArchiveConverter(BaseConverter):
    """Handles archiving, recompression, and extraction across archive containers."""

    name = "Archive & Package Engine"
    category = "Archives"

    def supported_inputs(self) -> Set[str]:
        return ARCHIVE_INPUTS

    def supported_outputs(self, input_ext: Optional[str] = None) -> Set[str]:
        if not input_ext:
            return ARCHIVE_OUTPUTS
        clean = input_ext.lower().lstrip(".")
        # Output can be any archive container except identical format
        return {o for o in ARCHIVE_OUTPUTS if o != clean}

    def get_default_options(self, source_ext: str, target_ext: str) -> Dict:
        return {
            "compression_level": 6,
        }

    def _extract_archive_to_dir(self, source_path: str, source_ext: str, temp_dir: str):
        """Extract input archive to directory."""
        if source_ext in ("zip", "apk", "jar"):
            with zipfile.ZipFile(source_path, "r") as zf:
                zf.extractall(temp_dir)

        elif source_ext == "tar":
            with tarfile.open(source_path, "r:") as tf:
                tf.extractall(temp_dir)

        elif source_ext == "gz":
            # Decompress single gz file
            out_file = os.path.join(temp_dir, os.path.splitext(os.path.basename(source_path))[0])
            with gzip.open(source_path, "rb") as f_in, open(out_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        elif source_ext == "bz2":
            out_file = os.path.join(temp_dir, os.path.splitext(os.path.basename(source_path))[0])
            with bz2.open(source_path, "rb") as f_in, open(out_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        elif source_ext == "deb":
            # Debian packages are ar archives
            import subprocess
            import sys
            # If ar/tar is available or extract via tar
            try:
                with tarfile.open(source_path) as tf:
                    tf.extractall(temp_dir)
            except Exception:
                pass

    def _create_archive_from_dir(self, source_dir: str, target_path: str, target_ext: str, options: Dict):
        """Package directory contents into target archive format."""
        if target_ext == "zip":
            with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(source_dir):
                    for file in files:
                        full_p = os.path.join(root, file)
                        rel_p = os.path.relpath(full_p, source_dir)
                        zf.write(full_p, rel_p)

        elif target_ext == "tar":
            with tarfile.open(target_path, "w:") as tf:
                tf.add(source_dir, arcname="")

        elif target_ext in ("tar.gz", "tgz", "gz"):
            # If creating gz from directory, create tar.gz
            with tarfile.open(target_path, "w:gz") as tf:
                tf.add(source_dir, arcname="")

        elif target_ext in ("tar.bz2", "tbz2", "bz2"):
            with tarfile.open(target_path, "w:bz2") as tf:
                tf.add(source_dir, arcname="")

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
        source_ext = os.path.splitext(source_path)[1].lower().lstrip(".")
        target_ext = target_format.lower().lstrip(".")
        opts = options or self.get_default_options(source_ext, target_ext)

        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                if progress_callback:
                    progress_callback(0.20, f"Unpacking {source_ext.upper()} archive...")

                if os.path.isdir(source_path):
                    # Source is a directory being compressed
                    extract_dir = source_path
                else:
                    self._extract_archive_to_dir(source_path, source_ext, temp_dir)
                    extract_dir = temp_dir

                if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                    return ConversionResult(success=False, error_message="Cancelled by user.")

                if progress_callback:
                    progress_callback(0.60, f"Compressing into {target_ext.upper()}...")

                self._create_archive_from_dir(extract_dir, target_path, target_ext, opts)

            if progress_callback:
                progress_callback(1.0, "Complete")

            return ConversionResult(
                success=True,
                output_path=target_path,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Archive conversion failed: {str(e)}",
                duration_seconds=time.time() - start_time,
            )
