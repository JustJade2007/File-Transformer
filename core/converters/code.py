"""Source code and markup converter to HTML, Markdown, PDF, and TXT."""
import html
import os
import time
from typing import Callable, Dict, List, Optional, Set

from .base import BaseConverter, ConversionResult

CODE_INPUTS = {
    "py", "js", "mjs", "ts", "java", "c", "cpp", "h", "cs", "php",
    "sh", "bat", "cmd", "ps1", "css", "html", "htm", "sql", "rb", "go", "rs"
}
CODE_OUTPUTS = {"html", "md", "pdf", "txt"}


class CodeConverter(BaseConverter):
    """Handles source code conversion to formatted HTML, Markdown, PDF, and TXT."""

    name = "Source Code Engine"
    category = "Code"

    def supported_inputs(self) -> Set[str]:
        return CODE_INPUTS

    def supported_outputs(self, input_ext: Optional[str] = None) -> Set[str]:
        return CODE_OUTPUTS

    def get_default_options(self, source_ext: str, target_ext: str) -> Dict:
        return {
            "include_line_numbers": True,
            "theme": "Dark",
        }

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
            if progress_callback:
                progress_callback(0.2, "Reading source code...")

            with open(source_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                return ConversionResult(success=False, error_message="Cancelled by user.")

            if progress_callback:
                progress_callback(0.6, f"Generating {target_ext.upper()} document...")

            if target_ext == "txt":
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)

            elif target_ext == "md":
                wrapped = f"```{source_ext}\n{content}\n```\n"
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(wrapped)

            elif target_ext == "html":
                lines = content.splitlines()
                table_rows = []
                for i, l in enumerate(lines, start=1):
                    escaped = html.escape(l)
                    table_rows.append(
                        f'<tr><td class="ln">{i}</td><td class="code"><code>{escaped}</code></td></tr>'
                    )

                code_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{os.path.basename(source_path)}</title>
<style>
body {{
  margin: 0;
  padding: 24px;
  background-color: #0f141c;
  color: #e6edf3;
  font-family: Consolas, 'Fira Code', 'Courier New', monospace;
}}
.container {{
  max-width: 1200px;
  margin: 0 auto;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  background-color: #161b22;
  border: 1px solid #30363d;
}}
.header {{
  padding: 12px 16px;
  background-color: #0d1117;
  border-bottom: 1px solid #30363d;
  font-size: 14px;
  font-weight: 600;
  color: #58a6ff;
}}
table {{
  width: 100%;
  border-collapse: collapse;
}}
td.ln {{
  width: 50px;
  text-align: right;
  padding: 2px 12px 2px 0;
  color: #6e7681;
  user-select: none;
  vertical-align: top;
  border-right: 1px solid #30363d;
}}
td.code {{
  padding: 2px 12px;
  white-space: pre-wrap;
  word-break: break-all;
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">{os.path.basename(source_path)} ({len(lines)} lines)</div>
  <table>
    {"".join(table_rows)}
  </table>
</div>
</body>
</html>"""
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(code_html)

            elif target_ext == "pdf":
                from .documents import DocumentConverter
                doc_conv = DocumentConverter()
                doc_conv._text_to_pdf(content, target_path, title=os.path.basename(source_path))

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
                error_message=f"Code conversion failed: {str(e)}",
                duration_seconds=time.time() - start_time,
            )
