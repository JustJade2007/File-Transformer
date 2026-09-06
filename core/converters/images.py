"""Image converter supporting raster formats, icons, PSD composite export, and PDF generation."""
import os
import time
from typing import Callable, Dict, List, Optional, Set
from PIL import Image

from .base import BaseConverter, ConversionResult

IMAGE_INPUTS = {
    "png", "jpg", "jpeg", "webp", "bmp", "ico", "tiff", "tif",
    "gif", "psd", "eps", "ppm", "pgm", "pbm"
}
IMAGE_OUTPUTS = {
    "png", "jpg", "jpeg", "webp", "bmp", "ico", "tiff", "gif", "pdf"
}


class ImageConverter(BaseConverter):
    """Handles raster image transformations, resizing, compression, and icon generation."""

    name = "Image Engine (Pillow)"
    category = "Images"

    def supported_inputs(self) -> Set[str]:
        return IMAGE_INPUTS

    def supported_outputs(self, input_ext: Optional[str] = None) -> Set[str]:
        return IMAGE_OUTPUTS

    def get_default_options(self, source_ext: str, target_ext: str) -> Dict:
        clean_target = target_ext.lower().lstrip(".")
        opts = {
            "quality": 92,
            "optimize": True,
            "resize_mode": "Original",  # "Original", "50%", "25%", "Custom"
            "custom_width": "",
            "custom_height": "",
        }
        if clean_target == "ico":
            opts["ico_sizes"] = "Standard (16, 32, 48, 64, 128, 256)"
        elif clean_target == "webp":
            opts["lossless"] = False
        return opts

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

        try:
            if progress_callback:
                progress_callback(0.15, "Opening image...")

            with Image.open(source_path) as img:
                if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                    return ConversionResult(success=False, error_message="Cancelled by user.")

                # Ensure output directory exists
                os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

                # Resize processing if requested
                resize_mode = opts.get("resize_mode", "Original")
                orig_w, orig_h = img.size
                target_w, target_h = orig_w, orig_h

                if resize_mode == "50%":
                    target_w, target_h = max(1, orig_w // 2), max(1, orig_h // 2)
                elif resize_mode == "25%":
                    target_w, target_h = max(1, orig_w // 4), max(1, orig_h // 4)
                elif resize_mode == "Custom":
                    cw = opts.get("custom_width")
                    ch = opts.get("custom_height")
                    if cw and ch:
                        try:
                            target_w, target_h = int(cw), int(ch)
                        except ValueError:
                            pass

                if (target_w, target_h) != (orig_w, orig_h):
                    if progress_callback:
                        progress_callback(0.40, f"Resizing to {target_w}x{target_h}...")
                    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

                if progress_callback:
                    progress_callback(0.60, f"Encoding {target_ext.upper()}...")

                # Format specific saves
                quality = int(opts.get("quality", 92))
                optimize = bool(opts.get("optimize", True))

                if target_ext in ("jpg", "jpeg"):
                    # Handle transparency by flattening onto clean white background
                    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        converted = img.convert("RGBA")
                        background.paste(converted, mask=converted.split()[3])
                        background.save(target_path, "JPEG", quality=quality, optimize=optimize)
                    else:
                        img.convert("RGB").save(target_path, "JPEG", quality=quality, optimize=optimize)

                elif target_ext == "png":
                    img.save(target_path, "PNG", optimize=optimize)

                elif target_ext == "webp":
                    lossless = bool(opts.get("lossless", False))
                    img.save(target_path, "WEBP", quality=quality, lossless=lossless)

                elif target_ext == "bmp":
                    # BMP does not support alpha in most standard viewers
                    if img.mode in ("RGBA", "LA"):
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        converted = img.convert("RGBA")
                        background.paste(converted, mask=converted.split()[3])
                        background.save(target_path, "BMP")
                    else:
                        img.convert("RGB").save(target_path, "BMP")

                elif target_ext == "ico":
                    # Windows icons require specific square dimensions
                    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                    img.save(target_path, format="ICO", sizes=icon_sizes)

                elif target_ext in ("tiff", "tif"):
                    img.save(target_path, format="TIFF")

                elif target_ext == "pdf":
                    # Convert single or multi-page image to PDF
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(target_path, "PDF", resolution=100.0)

                elif target_ext == "gif":
                    img.save(target_path, "GIF")

                else:
                    img.save(target_path)

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
                error_message=f"Image conversion failed: {str(e)}",
                duration_seconds=time.time() - start_time,
            )
