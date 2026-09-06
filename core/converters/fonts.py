"""Font converter supporting TTF, OTF, WOFF, and WOFF2 via fontTools."""
import os
import time
from typing import Callable, Dict, List, Optional, Set

from .base import BaseConverter, ConversionResult

FONT_FORMATS = {"ttf", "otf", "woff", "woff2"}


class FontConverter(BaseConverter):
    """Handles font conversions between TrueType, OpenType, WOFF, and WOFF2 formats."""

    name = "Font Engine (FontTools)"
    category = "Fonts"

    def supported_inputs(self) -> Set[str]:
        return FONT_FORMATS

    def supported_outputs(self, input_ext: Optional[str] = None) -> Set[str]:
        if not input_ext:
            return FONT_FORMATS
        clean = input_ext.lower().lstrip(".")
        return {f for f in FONT_FORMATS if f != clean}

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
        target_ext = target_format.lower().lstrip(".")

        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

        try:
            if progress_callback:
                progress_callback(0.25, "Loading font data...")

            from fontTools.ttLib import TTFont

            font = TTFont(source_path)

            if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                return ConversionResult(success=False, error_message="Cancelled by user.")

            if progress_callback:
                progress_callback(0.65, f"Transcoding font to {target_ext.upper()}...")

            if target_ext == "woff":
                font.flavor = "woff"
            elif target_ext == "woff2":
                font.flavor = "woff2"
            else:
                font.flavor = None

            font.save(target_path)
            font.close()

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
                error_message=f"Font conversion failed: {str(e)}",
                duration_seconds=time.time() - start_time,
            )
