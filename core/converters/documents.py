"""Document converter supporting DOCX, PDF, Markdown, HTML, TXT, RTF, and EPUB."""
import os
import re
import textwrap
import time
import zipfile
from typing import Callable, Dict, List, Optional, Set
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

from .base import BaseConverter, ConversionResult

DOC_INPUTS = {"pdf", "docx", "txt", "md", "html", "htm", "rtf", "odt", "epub"}
DOC_OUTPUTS = {"txt", "pdf", "docx", "html", "md", "png", "jpg", "jpeg", "webp", "bmp", "tiff"}

# File formats that do not support multiple pages in a single file
SINGLE_PAGE_FORMATS = {"png", "jpg", "jpeg", "webp", "bmp"}


class DocumentConverter(BaseConverter):
    """Handles text documents, eBooks, Markdown, and PDF document workflows."""

    name = "Document Engine (PyPDF & Docx)"
    category = "Documents"

    def supported_inputs(self) -> Set[str]:
        return DOC_INPUTS

    def supported_outputs(self, input_ext: Optional[str] = None) -> Set[str]:
        if not input_ext:
            return DOC_OUTPUTS
        clean = input_ext.lower().lstrip(".")
        if clean == "pdf":
            return {"txt", "docx", "html", "md", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"}
        elif clean == "docx":
            return {"txt", "md", "html", "pdf"}
        elif clean in ("txt", "md"):
            return {"html", "pdf", "docx", "txt"}
        elif clean in ("html", "htm"):
            return {"txt", "md", "pdf"}
        elif clean in ("rtf", "odt", "epub"):
            return {"txt", "md", "html", "docx"}
        return {"txt", "html", "md"}

    def get_default_options(self, source_ext: str, target_ext: str) -> Dict:
        clean_src = source_ext.lower().lstrip(".")
        clean_tgt = target_ext.lower().lstrip(".")
        if clean_src == "pdf" and clean_tgt in ("png", "jpg", "jpeg", "webp", "bmp", "tiff"):
            opts = {
                "dpi": 150,
                "quality": 92,
                "page_range": "All",
            }
            if clean_tgt == "tiff":
                opts["export_per_page"] = False
            return opts
        elif clean_src == "pdf" and clean_tgt == "pdf":
            return {"split_pages": False}
        elif clean_tgt == "pdf":
            return {"font_size": 11, "page_margin": 36}
        return {}

    def _parse_page_range(self, range_str: str, total_pages: int) -> List[int]:
        """Parse user-supplied page range string (e.g. 'All', '1-3, 5') into 0-based indices."""
        if not range_str or range_str.lower() == "all":
            return list(range(total_pages))
        indices: List[int] = []
        for part in range_str.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                sub = part.split("-", 1)
                try:
                    start = max(1, int(sub[0].strip()))
                    end = min(total_pages, int(sub[1].strip()))
                    for p in range(start, end + 1):
                        idx = p - 1
                        if 0 <= idx < total_pages and idx not in indices:
                            indices.append(idx)
                except ValueError:
                    pass
            else:
                try:
                    p = int(part)
                    idx = p - 1
                    if 0 <= idx < total_pages and idx not in indices:
                        indices.append(idx)
                except ValueError:
                    pass
        return indices if indices else list(range(total_pages))

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        text_parts = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_parts.append(f"--- Page {i + 1} ---\n" + text)
        return "\n\n".join(text_parts)

    def _extract_text_from_docx(self, docx_path: str) -> str:
        import docx
        doc = docx.Document(docx_path)
        lines = []
        for p in doc.paragraphs:
            lines.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                lines.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(lines)

    def _extract_text_from_epub(self, epub_path: str) -> str:
        """EPUB files are zip archives containing HTML/XHTML chapters."""
        text_parts = []
        with zipfile.ZipFile(epub_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith((".html", ".xhtml", ".htm")):
                    try:
                        content = zf.read(name).decode("utf-8", errors="replace")
                        clean = re.sub(r"<[^>]+>", " ", content)
                        clean = re.sub(r"\s+", " ", clean).strip()
                        if clean:
                            text_parts.append(clean)
                    except Exception:
                        pass
        return "\n\n".join(text_parts)

    def _extract_text_from_odt(self, odt_path: str) -> str:
        """ODT files are zip archives with content.xml."""
        with zipfile.ZipFile(odt_path, "r") as zf:
            if "content.xml" in zf.namelist():
                xml_data = zf.read("content.xml")
                root = ET.fromstring(xml_data)
                texts = [elem.text for elem in root.iter() if elem.text]
                return " ".join(texts)
        return ""

    def _extract_text_from_rtf(self, rtf_path: str) -> str:
        with open(rtf_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        clean = re.sub(r"\\[a-z0-9\-]+ ?", "", content)
        clean = re.sub(r"[{}\\]", "", clean)
        return clean.strip()

    def _text_to_docx(self, text: str, output_path: str):
        import docx
        doc = docx.Document()
        for line in text.splitlines():
            doc.add_paragraph(line)
        doc.save(output_path)

    def _pdf_to_docx(self, pdf_path: str, output_path: str):
        """Convert PDF to DOCX with page breaks preserving page boundaries."""
        import pypdf
        import docx
        reader = pypdf.PdfReader(pdf_path)
        doc = docx.Document()
        for idx, page in enumerate(reader.pages):
            if idx > 0:
                doc.add_page_break()
            text = page.extract_text()
            if text:
                for line in text.splitlines():
                    doc.add_paragraph(line)
            else:
                doc.add_paragraph(f"[Page {idx + 1}]")
        doc.save(output_path)

    def _pdf_to_md(self, pdf_path: str, output_path: str):
        """Convert PDF to Markdown with explicit page dividers."""
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        parts = []
        for idx, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            parts.append(f"## Page {idx + 1}\n\n{text}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(parts))

    def _pdf_to_html(self, pdf_path: str, output_path: str):
        """Convert PDF to styled HTML with individual page sections."""
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        page_htmls = []
        for idx, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            lines = [f"<p>{line}</p>" for line in text.splitlines() if line.strip()]
            page_content = "\n".join(lines) if lines else "<p><em>[No extractable text]</em></p>"
            page_htmls.append(f"""<section class="pdf-page" id="page-{idx + 1}">
  <div class="page-badge">Page {idx + 1} of {len(reader.pages)}</div>
  <div class="page-body">
    {page_content}
  </div>
</section>""")
        body = "\n<hr class=\"page-break\"/>\n".join(page_htmls)
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{os.path.basename(pdf_path)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #24292e; background: #f8fafc; }}
.pdf-page {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 36px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
.page-badge {{ display: inline-block; font-size: 12px; font-weight: 600; color: #475569; background: #f1f5f9; padding: 4px 12px; border-radius: 12px; margin-bottom: 20px; }}
.page-break {{ border: 0; height: 1px; background: #cbd5e1; margin: 32px 0; }}
p {{ margin: 0 0 12px 0; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_html)

    def _render_page_text_to_canvas(
        self,
        text: str,
        page_num: int,
        total_pages: int,
        width: int,
        height: int,
        title: str = "",
    ) -> Image.Image:
        """Render page text onto a clean, styled canvas."""
        canvas = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        margin_x = max(30, int(width * 0.06))
        margin_y = max(30, int(height * 0.05))
        content_width = width - 2 * margin_x

        # Header
        header_text = title if title else f"Page {page_num} of {total_pages}"
        draw.text((margin_x, margin_y), header_text[:70], fill=(120, 120, 120))
        page_indicator = f"Page {page_num}/{total_pages}"
        draw.text((max(margin_x + 100, width - margin_x - 120), margin_y), page_indicator, fill=(140, 140, 140))
        rule_y = margin_y + 26
        draw.line([(margin_x, rule_y), (width - margin_x, rule_y)], fill=(210, 215, 220), width=2)

        # Body text
        y = rule_y + 24
        line_height = max(18, int(height * 0.022))
        max_y = height - margin_y - 40
        chars_per_line = max(40, content_width // 10)

        lines = text.splitlines() if text.strip() else ["[Blank or Non-Text Page]"]
        for paragraph in lines:
            if y >= max_y:
                draw.text((margin_x, y), "... [content truncated for preview]", fill=(160, 160, 160))
                break
            if not paragraph.strip():
                y += line_height // 2
                continue
            wrapped_lines = textwrap.wrap(paragraph, width=chars_per_line)
            for line in wrapped_lines:
                if y >= max_y:
                    break
                draw.text((margin_x, y), line, fill=(30, 30, 30))
                y += line_height

        # Footer
        footer_y = height - margin_y
        draw.line([(margin_x, footer_y - 18), (width - margin_x, footer_y - 18)], fill=(230, 235, 240), width=1)
        footer_str = f"- {page_num} -"
        draw.text((width // 2 - 20, footer_y - 10), footer_str, fill=(140, 140, 140))

        return canvas

    def _save_image(self, img: Image.Image, path: str, ext: str, quality: int):
        """Save a PIL Image to disk in the desired format, handling transparency where needed."""
        clean_ext = ext.lower().lstrip(".")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        if clean_ext in ("jpg", "jpeg"):
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                conv = img.convert("RGBA")
                bg.paste(conv, mask=conv.split()[3])
                bg.save(path, "JPEG", quality=quality, optimize=True)
            else:
                img.convert("RGB").save(path, "JPEG", quality=quality, optimize=True)
        elif clean_ext == "png":
            img.save(path, "PNG", optimize=True)
        elif clean_ext == "webp":
            img.save(path, "WEBP", quality=quality)
        elif clean_ext == "bmp":
            img.convert("RGB").save(path, "BMP")
        elif clean_ext in ("tiff", "tif"):
            img.save(path, "TIFF")
        else:
            img.save(path)

    def _convert_pdf_to_images(
        self,
        source_path: str,
        target_path: str,
        target_format: str,
        options: Dict,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[object] = None,
    ) -> ConversionResult:
        """
        Convert PDF pages to image format.
        If target format does not support multiple pages (PNG, JPG, WEBP, BMP),
        automatically exports one file per page as '{basename}_page_{N}.{ext}'
        (or directly '{basename}.{ext}' if PDF has only 1 page).
        """
        import pypdf
        start_time = time.time()
        reader = pypdf.PdfReader(source_path)
        total_pages = len(reader.pages)
        if total_pages == 0:
            return ConversionResult(success=False, error_message="PDF contains no pages.")

        dpi = int(options.get("dpi", 150))
        quality = int(options.get("quality", 92))
        page_range_str = str(options.get("page_range", "All")).strip()

        page_indices = self._parse_page_range(page_range_str, total_pages)
        if not page_indices:
            page_indices = list(range(total_pages))

        dest_dir = os.path.dirname(os.path.abspath(target_path))
        base_name = os.path.splitext(os.path.basename(target_path))[0]
        ext = target_format.lower().lstrip(".")
        os.makedirs(dest_dir, exist_ok=True)

        is_single_page_target = ext in SINGLE_PAGE_FORMATS
        export_per_page = options.get("export_per_page", is_single_page_target)

        # Check if pypdfium2 is available for full-fidelity vector rasterization
        pdfium_doc = None
        try:
            import pypdfium2 as pdfium
            pdfium_doc = pdfium.PdfDocument(source_path)
        except Exception:
            pdfium_doc = None

        rendered_images: List[Image.Image] = []
        exported_paths: List[str] = []

        total_selected = len(page_indices)
        for step_idx, page_idx in enumerate(page_indices):
            if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                return ConversionResult(success=False, error_message="Cancelled by user.")

            if progress_callback:
                frac = (step_idx + 0.1) / total_selected
                progress_callback(frac, f"Exporting page {page_idx + 1} of {total_pages}...")

            img = None

            # 1. Try pypdfium2 high-fidelity rendering
            if pdfium_doc is not None:
                try:
                    p_page = pdfium_doc[page_idx]
                    img = p_page.render(scale=dpi / 72.0).to_pil()
                except Exception:
                    img = None

            # 2. Fallback using pypdf & Pillow
            if img is None:
                page_obj = reader.pages[page_idx]
                pt_w = float(getattr(page_obj.mediabox, "width", 612))
                pt_h = float(getattr(page_obj.mediabox, "height", 792))
                w_px = max(200, int(pt_w / 72.0 * dpi))
                h_px = max(200, int(pt_h / 72.0 * dpi))

                page_images = list(page_obj.images)
                page_text = page_obj.extract_text() or ""

                if len(page_images) == 1 and len(page_text.strip()) < 50:
                    # Predominantly an embedded raster image (scanned page)
                    try:
                        img = page_images[0].image
                    except Exception:
                        img = None

                if img is None:
                    # Clean typographical canvas rendering
                    img = self._render_page_text_to_canvas(
                        text=page_text,
                        page_num=page_idx + 1,
                        total_pages=total_pages,
                        width=w_px,
                        height=h_px,
                        title=os.path.basename(source_path),
                    )

            # Determine destination path for this page
            if export_per_page:
                if total_selected == 1:
                    page_file_path = target_path
                else:
                    page_file_path = os.path.join(dest_dir, f"{base_name}_page_{page_idx + 1}.{ext}")
                self._save_image(img, page_file_path, ext, quality)
                exported_paths.append(page_file_path)
            else:
                rendered_images.append(img)

        # Multi-page image format (e.g. TIFF) where export_per_page is False
        if not export_per_page and rendered_images:
            if ext in ("tiff", "tif"):
                rendered_images[0].save(
                    target_path,
                    save_all=True,
                    append_images=rendered_images[1:],
                    format="TIFF",
                )
                exported_paths.append(target_path)
            else:
                self._save_image(rendered_images[0], target_path, ext, quality)
                exported_paths.append(target_path)

        if progress_callback:
            progress_callback(1.0, "Complete")

        return ConversionResult(
            success=True,
            output_path=exported_paths[0] if exported_paths else target_path,
            output_paths=exported_paths,
            duration_seconds=time.time() - start_time,
            details={
                "output_files": exported_paths,
                "page_count": len(exported_paths),
                "engine": "pypdfium2" if pdfium_doc is not None else "pypdf+pillow",
            },
        )

    def _pdf_split_or_copy(self, pdf_path: str, output_path: str, options: Dict) -> ConversionResult:
        """Handle PDF -> PDF workflows (copy/rewrite, or split per page)."""
        import pypdf
        start_time = time.time()
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        split_pages = bool(options.get("split_pages", False))

        if split_pages and total_pages > 1:
            dest_dir = os.path.dirname(os.path.abspath(output_path))
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            exported = []
            for idx, page in enumerate(reader.pages):
                writer = pypdf.PdfWriter()
                writer.add_page(page)
                page_path = os.path.join(dest_dir, f"{base_name}_page_{idx + 1}.pdf")
                with open(page_path, "wb") as fp:
                    writer.write(fp)
                exported.append(page_path)
            return ConversionResult(
                success=True,
                output_path=exported[0],
                output_paths=exported,
                duration_seconds=time.time() - start_time,
                details={"output_files": exported, "page_count": len(exported)},
            )
        else:
            writer = pypdf.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            with open(output_path, "wb") as fp:
                writer.write(fp)
            return ConversionResult(
                success=True,
                output_path=output_path,
                output_paths=[output_path],
                duration_seconds=time.time() - start_time,
                details={"output_files": [output_path], "page_count": 1},
            )

    def _text_to_pdf(self, text: str, output_path: str, title: str = "Document"):
        """Pure Python PDF generation via basic PDF stream or reportlab if present."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(output_path, pagesize=letter)
            width, height = letter
            y = height - 50
            for line in text.splitlines():
                if y < 50:
                    c.showPage()
                    y = height - 50
                safe_line = line.encode("latin-1", "replace").decode("latin-1")
                c.drawString(50, y, safe_line[:95])
                y -= 14
            c.save()
        except ImportError:
            self._minimal_pdf_write(text, output_path, title)

    def _minimal_pdf_write(self, text: str, output_path: str, title: str):
        lines = text.splitlines()
        max_lines_per_page = 50
        pages = [lines[i:i + max_lines_per_page] for i in range(0, max(1, len(lines)), max_lines_per_page)]

        objects = []
        page_obj_ids = []

        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

        cur_id = 3
        page_stream_tuples = []
        for p in pages:
            text_cmds = ["BT", "/F1 10 Tf", "50 750 Td", "14 TL"]
            for l in p:
                sanitized = l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                sanitized = sanitized.encode("latin-1", "replace").decode("latin-1")
                text_cmds.append(f"({sanitized[:90]}) '")
            text_cmds.append("ET")
            stream_data = "\n".join(text_cmds).encode("latin-1")

            page_id = cur_id
            stream_id = cur_id + 1
            cur_id += 2

            page_obj_ids.append(page_id)
            page_stream_tuples.append((page_id, stream_id, stream_data))

        buf = bytearray(b"%PDF-1.4\n")
        offsets = {}

        offsets[1] = len(buf)
        buf.extend(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        offsets[2] = len(buf)
        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        buf.extend(f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {len(pages)} >>\nendobj\n".encode("latin-1"))

        font_id = cur_id
        offsets[font_id] = len(buf)
        buf.extend(f"{font_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode("latin-1"))

        for pid, sid, sdata in page_stream_tuples:
            offsets[pid] = len(buf)
            buf.extend(f"{pid} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {sid} 0 R >>\nendobj\n".encode("latin-1"))

            offsets[sid] = len(buf)
            buf.extend(f"{sid} 0 obj\n<< /Length {len(sdata)} >>\nstream\n".encode("latin-1"))
            buf.extend(sdata)
            buf.extend(b"\nendstream\nendobj\n")

        xref_offset = len(buf)
        total_objects = font_id + 1
        buf.extend(f"xref\n0 {total_objects}\n0000000000 65535 f \n".encode("latin-1"))
        for oid in range(1, total_objects):
            offset = offsets.get(oid, 0)
            buf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

        buf.extend(f"trailer\n<< /Size {total_objects} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1"))

        with open(output_path, "wb") as f:
            f.write(buf)

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
            # Handle PDF as source
            if source_ext == "pdf":
                if target_ext in ("png", "jpg", "jpeg", "webp", "bmp", "tiff"):
                    return self._convert_pdf_to_images(
                        source_path=source_path,
                        target_path=target_path,
                        target_format=target_ext,
                        options=opts,
                        progress_callback=progress_callback,
                        cancel_event=cancel_event,
                    )
                elif target_ext == "docx":
                    if progress_callback:
                        progress_callback(0.3, "Converting PDF to DOCX...")
                    self._pdf_to_docx(source_path, target_path)
                    if progress_callback:
                        progress_callback(1.0, "Complete")
                    return ConversionResult(
                        success=True,
                        output_path=target_path,
                        output_paths=[target_path],
                        duration_seconds=time.time() - start_time,
                    )
                elif target_ext == "md":
                    if progress_callback:
                        progress_callback(0.3, "Converting PDF to Markdown...")
                    self._pdf_to_md(source_path, target_path)
                    if progress_callback:
                        progress_callback(1.0, "Complete")
                    return ConversionResult(
                        success=True,
                        output_path=target_path,
                        output_paths=[target_path],
                        duration_seconds=time.time() - start_time,
                    )
                elif target_ext == "html":
                    if progress_callback:
                        progress_callback(0.3, "Converting PDF to HTML...")
                    self._pdf_to_html(source_path, target_path)
                    if progress_callback:
                        progress_callback(1.0, "Complete")
                    return ConversionResult(
                        success=True,
                        output_path=target_path,
                        output_paths=[target_path],
                        duration_seconds=time.time() - start_time,
                    )
                elif target_ext == "pdf":
                    return self._pdf_split_or_copy(source_path, target_path, opts)

            # Standard document input reading
            if progress_callback:
                progress_callback(0.2, f"Reading {source_ext.upper()}...")

            text_content = ""
            if source_ext == "pdf":
                text_content = self._extract_text_from_pdf(source_path)
            elif source_ext == "docx":
                text_content = self._extract_text_from_docx(source_path)
            elif source_ext == "epub":
                text_content = self._extract_text_from_epub(source_path)
            elif source_ext == "odt":
                text_content = self._extract_text_from_odt(source_path)
            elif source_ext == "rtf":
                text_content = self._extract_text_from_rtf(source_path)
            elif source_ext in ("txt", "md", "html", "htm"):
                with open(source_path, "r", encoding="utf-8", errors="replace") as f:
                    text_content = f.read()

            if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                return ConversionResult(success=False, error_message="Cancelled by user.")

            if progress_callback:
                progress_callback(0.6, f"Converting to {target_ext.upper()}...")

            if target_ext == "txt":
                if source_ext in ("html", "htm"):
                    clean = re.sub(r"<[^>]+>", " ", text_content)
                    clean = re.sub(r"\s+", " ", clean).strip()
                    text_content = clean
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

            elif target_ext == "md":
                if source_ext in ("html", "htm"):
                    text_content = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", text_content, flags=re.I)
                    text_content = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", text_content, flags=re.I)
                    text_content = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text_content, flags=re.I)
                    text_content = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text_content, flags=re.I)
                    text_content = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", text_content, flags=re.I)
                    text_content = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text_content, flags=re.I)
                    text_content = re.sub(r"<[^>]+>", "", text_content)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

            elif target_ext == "html":
                if source_ext == "md":
                    import markdown
                    html_body = markdown.markdown(text_content, extensions=["tables", "fenced_code"])
                else:
                    lines = [f"<p>{line}</p>" for line in text_content.splitlines() if line.strip()]
                    html_body = "\n".join(lines)

                full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{os.path.basename(source_path)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #24292e; }}
pre {{ background: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; }}
code {{ font-family: Consolas, 'Liberation Mono', Menlo, Courier, monospace; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
th, td {{ border: 1px solid #dfe2e5; padding: 6px 13px; }}
th {{ background: #f6f8fa; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(full_html)

            elif target_ext == "docx":
                self._text_to_docx(text_content, target_path)

            elif target_ext == "pdf":
                self._text_to_pdf(text_content, target_path, title=os.path.basename(source_path))

            if progress_callback:
                progress_callback(1.0, "Complete")

            return ConversionResult(
                success=True,
                output_path=target_path,
                output_paths=[target_path],
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Document conversion failed: {str(e)}",
                duration_seconds=time.time() - start_time,
            )
