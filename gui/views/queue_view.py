"""
Queue View — main conversion workspace with drag-and-drop, file table,
batch format selector, per-item overrides, progress tracking, and output controls.
"""
import os
import subprocess
import sys
import tkinter as tk
import uuid
from tkinter import filedialog
from typing import Dict, List, Optional

import customtkinter as ctk

from gui import theme as T
from core.engine import ConversionEngine, ConversionTask, TaskStatus
from core.registry import FormatRegistry

try:
    from tkinterdnd2 import DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


class AdvancedOptionsDialog(ctk.CTkToplevel):
    """Modal popup for per-format conversion options."""

    def __init__(self, parent, source_ext: str, target_ext: str, current_options: Dict):
        super().__init__(parent)
        self.title("Advanced Options")
        self.geometry("420x380")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=T.c("bg_secondary"))
        self.result: Optional[Dict] = None

        self._source_ext = source_ext
        self._target_ext = target_ext
        self._opts = dict(current_options)

        self._build(source_ext, target_ext, self._opts)

    def _build(self, src: str, tgt: str, opts: Dict):
        ctk.CTkLabel(
            self, text=f"  .{src}  →  .{tgt}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=T.c("accent"),
        ).pack(pady=(20, 4), padx=20, anchor="w")

        ctk.CTkLabel(
            self,
            text="Conversion Settings",
            font=ctk.CTkFont(size=12),
            text_color=T.c("text_secondary"),
        ).pack(padx=20, anchor="w")

        frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=16, pady=8)

        self._widgets: Dict = {}

        for key, val in opts.items():
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=3)

            label_text = key.replace("_", " ").title()
            ctk.CTkLabel(row, text=label_text, width=140, anchor="w",
                         text_color=T.c("text_secondary")).pack(side="left")

            if isinstance(val, bool):
                var = tk.BooleanVar(value=val)
                widget = ctk.CTkSwitch(row, text="", variable=var,
                                       fg_color=T.c("accent_dim"),
                                       progress_color=T.c("accent"))
                widget.pack(side="left")
                self._widgets[key] = var

            elif isinstance(val, int):
                var = tk.IntVar(value=val)
                widget = ctk.CTkEntry(row, textvariable=var, width=80,
                                      fg_color=T.c("bg_card"),
                                      border_color=T.c("border"),
                                      text_color=T.c("text_primary"))
                widget.pack(side="left")
                self._widgets[key] = var

            elif isinstance(val, float):
                var = tk.StringVar(value=str(val))
                widget = ctk.CTkEntry(row, textvariable=var, width=80,
                                      fg_color=T.c("bg_card"),
                                      border_color=T.c("border"),
                                      text_color=T.c("text_primary"))
                widget.pack(side="left")
                self._widgets[key] = var

            elif isinstance(val, str) and val.startswith("Original"):
                # Drop-down choices
                if key == "video_resolution":
                    choices = ["Original", "1080p", "720p", "480p"]
                elif key == "video_quality":
                    choices = ["Ultra High (CRF 18)", "High (CRF 20)", "Medium (CRF 23)", "Low (CRF 28)"]
                elif key == "fps":
                    choices = ["Original", "60", "30", "24", "15"]
                else:
                    choices = [val]

                var = tk.StringVar(value=val)
                widget = ctk.CTkComboBox(row, values=choices, variable=var, width=160,
                                         fg_color=T.c("bg_card"),
                                         border_color=T.c("border"),
                                         text_color=T.c("text_primary"),
                                         button_color=T.c("accent_dim"),
                                         dropdown_fg_color=T.c("bg_card"))
                widget.pack(side="left")
                self._widgets[key] = var

            else:
                var = tk.StringVar(value=str(val))
                widget = ctk.CTkEntry(row, textvariable=var, width=120,
                                      fg_color=T.c("bg_card"),
                                      border_color=T.c("border"),
                                      text_color=T.c("text_primary"))
                widget.pack(side="left")
                self._widgets[key] = var

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(4, 16))
        ctk.CTkButton(btn_frame, text="Cancel", width=90,
                      fg_color=T.c("bg_card"), hover_color=T.c("bg_hover"),
                      text_color=T.c("text_secondary"),
                      command=self.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="Apply", width=90,
                      fg_color=T.c("accent"), hover_color=T.c("accent_hover"),
                      text_color="#ffffff",
                      command=self._apply).pack(side="left")

    def _apply(self):
        result = {}
        for key, var in self._widgets.items():
            val = var.get()
            orig = self._opts[key]
            if isinstance(orig, bool):
                result[key] = bool(val)
            elif isinstance(orig, int):
                try:
                    result[key] = int(val)
                except (ValueError, tk.TclError):
                    result[key] = orig
            elif isinstance(orig, float):
                try:
                    result[key] = float(val)
                except (ValueError, tk.TclError):
                    result[key] = orig
            else:
                result[key] = val
        self.result = result
        self.destroy()


# ─── Queue Row ────────────────────────────────────────────────────────────────

class QueueRow(ctk.CTkFrame):
    """A single file row in the conversion queue table."""

    STATUS_COLORS = {
        TaskStatus.QUEUED:     ("#5a6a7a", "#1c2333"),
        TaskStatus.CONVERTING: ("#58a6ff", "#0f2040"),
        TaskStatus.DONE:       ("#3fb950", "#0d2818"),
        TaskStatus.ERROR:      ("#f85149", "#2d0f0e"),
        TaskStatus.CANCELLED:  ("#8b949e", "#1c1f26"),
    }

    def __init__(self, parent, task: ConversionTask, valid_targets: Dict, on_remove, on_advanced):
        super().__init__(parent,
                         fg_color=T.c("bg_card"),
                         corner_radius=8,
                         border_width=1,
                         border_color=T.c("border"))

        self._task = task
        self._on_remove = on_remove
        self._on_advanced = on_advanced

        self.grid_columnconfigure(1, weight=1)
        self.pack(fill="x", padx=0, pady=3)

        # Icon / type badge
        src_ext = os.path.splitext(task.source_path)[1].upper().lstrip(".")
        ext_label = ctk.CTkLabel(self, text=src_ext,
                                  width=44, height=44,
                                  fg_color=T.c("accent_dim"),
                                  corner_radius=6,
                                  text_color=T.c("accent"),
                                  font=ctk.CTkFont(size=11, weight="bold"))
        ext_label.grid(row=0, column=0, rowspan=2, padx=(10, 8), pady=10, sticky="ns")

        # Filename and size
        fname = os.path.basename(task.source_path)
        try:
            fsize = os.path.getsize(task.source_path)
            size_str = self._fmt_size(fsize)
        except OSError:
            size_str = "?"

        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(10, 2))
        ctk.CTkLabel(name_frame, text=fname, anchor="w",
                     text_color=T.c("text_primary"),
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkLabel(name_frame, text=f"  {size_str}",
                     text_color=T.c("text_muted"),
                     font=ctk.CTkFont(size=11)).pack(side="left")

        # Progress + status
        self._status_label = ctk.CTkLabel(self, text="Queued",
                                           text_color=T.c("text_secondary"),
                                           font=ctk.CTkFont(size=11))
        self._status_label.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(0, 6))

        self._progress_bar = ctk.CTkProgressBar(self, width=200, height=6,
                                                  progress_color=T.c("accent"),
                                                  fg_color=T.c("progress_track"))
        self._progress_bar.set(0)
        self._progress_bar.grid(row=1, column=1, sticky="e", padx=(100, 8), pady=(0, 8))

        # Target format dropdown
        all_targets = []
        for targets in valid_targets.values():
            all_targets.extend(targets)
        all_targets = sorted(set(all_targets))

        self._target_var = tk.StringVar(value=task.target_format if task.target_format in all_targets else (all_targets[0] if all_targets else ""))
        task.target_format = self._target_var.get()
        self._target_var.trace_add("write", self._on_target_change)

        target_combo = ctk.CTkComboBox(self, values=all_targets,
                                        variable=self._target_var,
                                        width=90,
                                        fg_color=T.c("bg_secondary"),
                                        border_color=T.c("border"),
                                        text_color=T.c("text_primary"),
                                        button_color=T.c("accent_dim"),
                                        dropdown_fg_color=T.c("bg_secondary"))
        target_combo.grid(row=0, column=2, padx=6, pady=10, sticky="e")

        # Advanced button
        adv_btn = ctk.CTkButton(self, text="⚙", width=30, height=30,
                                 fg_color=T.c("bg_secondary"),
                                 hover_color=T.c("bg_hover"),
                                 text_color=T.c("text_secondary"),
                                 corner_radius=6,
                                 command=self._open_advanced)
        adv_btn.grid(row=0, column=3, padx=(0, 6), pady=10)

        # Remove button
        rm_btn = ctk.CTkButton(self, text="✕", width=30, height=30,
                                fg_color=T.c("bg_secondary"),
                                hover_color=T.c("badge_error"),
                                text_color=T.c("text_secondary"),
                                corner_radius=6,
                                command=lambda: self._on_remove(task.task_id))
        rm_btn.grid(row=0, column=4, padx=(0, 10), pady=10)

    def _fmt_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / 1024 ** 2:.1f} MB"
        return f"{size_bytes / 1024 ** 3:.2f} GB"

    def _on_target_change(self, *_):
        self._task.target_format = self._target_var.get()

    def _open_advanced(self):
        src_ext = os.path.splitext(self._task.source_path)[1].lower().lstrip(".")
        tgt_ext = self._target_var.get()
        self._on_advanced(self._task, src_ext, tgt_ext)

    def update_progress(self, frac: float, status_text: str, status: TaskStatus):
        self._progress_bar.set(frac)
        self._status_label.configure(text=status_text)
        colors = self.STATUS_COLORS.get(status, ("#8b949e", "#1c1f26"))
        self._progress_bar.configure(progress_color=colors[0])


# ─── Queue View ───────────────────────────────────────────────────────────────

class QueueView(ctk.CTkFrame):
    """Main conversion queue view with drag-and-drop, batch controls, and progress."""

    def __init__(self, parent, engine: ConversionEngine):
        super().__init__(parent, fg_color="transparent")
        self._engine = engine
        self._registry = FormatRegistry()
        self._rows: Dict[str, QueueRow] = {}
        self._task_options: Dict[str, Dict] = {}
        self._output_dir: Optional[str] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_dropzone()
        self._build_batch_bar()
        self._build_table()
        self._build_bottom_bar()

    # ── Layout builders ──────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="File Transformer",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=T.c("text_primary")).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(bar, text="Local • Private • No Limits",
                     font=ctk.CTkFont(size=12),
                     text_color=T.c("accent")).grid(row=0, column=1, padx=12, sticky="w")

    def _build_dropzone(self):
        self._dropzone = ctk.CTkFrame(self,
                                       fg_color=T.c("dropzone_bg"),
                                       corner_radius=16,
                                       border_width=2,
                                       border_color=T.c("dropzone_border"))
        self._dropzone.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._dropzone.grid_columnconfigure(0, weight=1)
        self._dropzone.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(self._dropzone, fg_color="transparent")
        inner.grid(row=0, column=0)

        ctk.CTkLabel(inner, text="⬇",
                     font=ctk.CTkFont(size=48),
                     text_color=T.c("dropzone_border")).pack()
        ctk.CTkLabel(inner, text="Drop files here",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T.c("text_primary")).pack(pady=(4, 2))
        ctk.CTkLabel(inner, text="or click to browse",
                     font=ctk.CTkFont(size=13),
                     text_color=T.c("text_secondary")).pack()

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=16)

        ctk.CTkButton(btn_row, text="📂  Browse Files",
                      fg_color=T.c("accent"), hover_color=T.c("accent_hover"),
                      text_color="#ffffff", font=ctk.CTkFont(size=13, weight="bold"),
                      corner_radius=8, height=38, width=160,
                      command=self._browse_files).pack(side="left", padx=8)

        ctk.CTkButton(btn_row, text="📁  Browse Folder",
                      fg_color=T.c("bg_card"), hover_color=T.c("bg_hover"),
                      text_color=T.c("text_primary"), font=ctk.CTkFont(size=13),
                      corner_radius=8, height=38, width=160,
                      command=self._browse_folder).pack(side="left", padx=8)

        # Wire up drag-and-drop
        if DND_AVAILABLE:
            try:
                self._dropzone.drop_target_register(DND_FILES)
                self._dropzone.dnd_bind("<<Drop>>", self._on_dnd_drop)
                inner.drop_target_register(DND_FILES)
                inner.dnd_bind("<<Drop>>", self._on_dnd_drop)
            except Exception:
                pass

        # Bind click on dropzone
        self._dropzone.bind("<Button-1>", lambda _: self._browse_files())
        inner.bind("<Button-1>", lambda _: self._browse_files())

    def _build_batch_bar(self):
        """Batch controls — shown when queue has items."""
        self._batch_frame = ctk.CTkFrame(self, fg_color=T.c("bg_secondary"),
                                          corner_radius=8)
        # Not shown initially; shown when queue is populated

    def _build_table(self):
        self._table_frame_outer = ctk.CTkFrame(self, fg_color="transparent")
        # Not placed initially; replaces dropzone when files are added

        header = ctk.CTkFrame(self._table_frame_outer,
                               fg_color=T.c("bg_secondary"),
                               corner_radius=8)
        header.pack(fill="x", pady=(0, 4))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="File", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.c("text_secondary")).grid(row=0, column=1, padx=60, pady=8, sticky="w")
        ctk.CTkLabel(header, text="Target", anchor="center",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T.c("text_secondary")).grid(row=0, column=2, padx=8, pady=8)
        ctk.CTkLabel(header, text="", width=30).grid(row=0, column=3)
        ctk.CTkLabel(header, text="", width=30).grid(row=0, column=4, padx=10)

        # Add-more button inside table header
        ctk.CTkButton(header, text="+ Add Files", width=100, height=28,
                      fg_color=T.c("accent_dim"), hover_color=T.c("accent"),
                      text_color=T.c("accent"), font=ctk.CTkFont(size=12),
                      corner_radius=6,
                      command=self._browse_files).grid(row=0, column=5, padx=8, pady=6)

        self._table_scroll = ctk.CTkScrollableFrame(self._table_frame_outer,
                                                     fg_color="transparent")
        self._table_scroll.pack(fill="both", expand=True)
        self._table_scroll.grid_columnconfigure(0, weight=1)

    def _build_bottom_bar(self):
        self._bottom = ctk.CTkFrame(self, fg_color=T.c("bg_secondary"),
                                     corner_radius=10, border_width=1,
                                     border_color=T.c("border"))
        self._bottom.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self._bottom.grid_columnconfigure(2, weight=1)

        # Output dir section
        self._output_label = ctk.CTkLabel(self._bottom, text="📂 Same folder as source",
                                           text_color=T.c("text_secondary"),
                                           font=ctk.CTkFont(size=12))
        self._output_label.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        ctk.CTkButton(self._bottom, text="Change…", width=80, height=28,
                      fg_color=T.c("bg_card"), hover_color=T.c("bg_hover"),
                      text_color=T.c("text_secondary"), font=ctk.CTkFont(size=11),
                      corner_radius=6,
                      command=self._choose_output_dir).grid(row=0, column=1, padx=(0, 12), pady=10)

        # Control buttons
        self._btn_start = ctk.CTkButton(self._bottom, text="▶  Convert All",
                                         width=140, height=36,
                                         fg_color=T.c("accent"), hover_color=T.c("accent_hover"),
                                         text_color="#ffffff",
                                         font=ctk.CTkFont(size=13, weight="bold"),
                                         corner_radius=8,
                                         command=self._start_conversion)
        self._btn_start.grid(row=0, column=3, padx=6, pady=8)

        self._btn_cancel = ctk.CTkButton(self._bottom, text="⏹  Cancel",
                                          width=100, height=36,
                                          fg_color=T.c("bg_card"), hover_color=T.c("bg_hover"),
                                          text_color=T.c("error"),
                                          font=ctk.CTkFont(size=13),
                                          corner_radius=8,
                                          command=self._cancel_all)
        self._btn_cancel.grid(row=0, column=4, padx=6, pady=8)

        self._btn_clear = ctk.CTkButton(self._bottom, text="🗑  Clear",
                                         width=90, height=36,
                                         fg_color=T.c("bg_card"), hover_color=T.c("bg_hover"),
                                         text_color=T.c("text_secondary"),
                                         font=ctk.CTkFont(size=13),
                                         corner_radius=8,
                                         command=self._clear_queue)
        self._btn_clear.grid(row=0, column=5, padx=(0, 12), pady=8)

        self._btn_open = ctk.CTkButton(self._bottom, text="📂 Open Output",
                                        width=120, height=36,
                                        fg_color=T.c("bg_card"), hover_color=T.c("bg_hover"),
                                        text_color=T.c("success"),
                                        font=ctk.CTkFont(size=13),
                                        corner_radius=8,
                                        command=self._open_output_folder,
                                        state="disabled")
        self._btn_open.grid(row=0, column=6, padx=(0, 12), pady=8)

    # ── File management ───────────────────────────────────────────────────────

    def _browse_files(self):
        paths = filedialog.askopenfilenames(
            title="Select files to convert",
            filetypes=[("All Files", "*.*")]
        )
        if paths:
            for p in paths:
                self._add_file(p)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select a folder to add all files from")
        if folder:
            for root, _, files in os.walk(folder):
                for fname in files:
                    self._add_file(os.path.join(root, fname))

    def _on_dnd_drop(self, event):
        raw = event.data
        # tkinterdnd2 returns space-separated paths, curly-bracketed if they contain spaces
        import re
        paths = re.findall(r'\{([^}]+)\}|(\S+)', raw)
        for match in paths:
            p = match[0] or match[1]
            if p:
                p = p.strip()
                if os.path.isfile(p):
                    self._add_file(p)
                elif os.path.isdir(p):
                    for root, _, files in os.walk(p):
                        for fname in files:
                            self._add_file(os.path.join(root, fname))

    def _add_file(self, path: str):
        """Add a single file to the queue and create its row widget."""
        if not os.path.isfile(path):
            return
        src_ext = os.path.splitext(path)[1].lower().lstrip(".")
        valid_targets = self._registry.get_valid_targets(src_ext)
        if not valid_targets:
            return  # Unsupported format

        # Default target = first option from first category
        default_target = ""
        for targets in valid_targets.values():
            if targets:
                default_target = targets[0]
                break

        task = ConversionTask(
            task_id=str(uuid.uuid4()),
            source_path=path,
            target_format=default_target,
            output_dir=self._output_dir,
        )

        row = QueueRow(
            self._table_scroll,
            task=task,
            valid_targets=valid_targets,
            on_remove=self._remove_task,
            on_advanced=self._open_advanced,
        )

        self._rows[task.task_id] = row
        self._switch_to_table()

    def _remove_task(self, task_id: str):
        row = self._rows.pop(task_id, None)
        if row:
            row.destroy()
        if not self._rows:
            self._switch_to_dropzone()

    def _open_advanced(self, task: ConversionTask, src_ext: str, tgt_ext: str):
        from core.registry import FormatRegistry
        reg = FormatRegistry()
        converter = reg.find_converter(src_ext, tgt_ext)
        if not converter:
            return
        defaults = converter.get_default_options(src_ext, tgt_ext)
        current_opts = self._task_options.get(task.task_id, dict(defaults))

        dialog = AdvancedOptionsDialog(self.winfo_toplevel(), src_ext, tgt_ext, current_opts)
        self.wait_window(dialog)
        if dialog.result is not None:
            self._task_options[task.task_id] = dialog.result
            task.options = dialog.result

    # ── View switching ────────────────────────────────────────────────────────

    def _switch_to_table(self):
        self._dropzone.grid_forget()
        self._table_frame_outer.grid(row=1, column=0, sticky="nsew", pady=0)
        self.grid_rowconfigure(1, weight=1)

    def _switch_to_dropzone(self):
        self._table_frame_outer.grid_forget()
        self._dropzone.grid(row=1, column=0, sticky="nsew", pady=0)
        self.grid_rowconfigure(1, weight=1)

    # ── Output directory ─────────────────────────────────────────────────────

    def _choose_output_dir(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self._output_dir = folder
            short = folder if len(folder) < 50 else "…" + folder[-47:]
            self._output_label.configure(text=f"📂 {short}")
            # Update all pending tasks
            for tid, row in self._rows.items():
                task = row._task
                if task.status == TaskStatus.QUEUED:
                    task.output_dir = folder

    # ── Conversion controls ───────────────────────────────────────────────────

    def _start_conversion(self):
        """Submit all queued tasks to the engine."""
        self._btn_open.configure(state="disabled")
        for tid, row in self._rows.items():
            task = row._task
            if task.status == TaskStatus.QUEUED:
                task.output_dir = self._output_dir
                self._engine.submit(
                    task,
                    on_progress=self._on_task_progress,
                    on_complete=self._on_task_complete,
                )

    def _cancel_all(self):
        self._engine.cancel_all()

    def _clear_queue(self):
        self._engine.cancel_all()
        for tid, row in list(self._rows.items()):
            row.destroy()
        self._rows.clear()
        self._task_options.clear()
        self._switch_to_dropzone()
        self._btn_open.configure(state="disabled")

    def _open_output_folder(self):
        folder = self._output_dir
        if not folder:
            # Find last completed task's directory
            for tid, row in self._rows.items():
                task = row._task
                if task.output_path and os.path.exists(task.output_path):
                    folder = os.path.dirname(task.output_path)
                    break
        if folder and os.path.isdir(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    # ── Engine callbacks (called from worker threads) ─────────────────────────

    def _on_task_progress(self, task_id: str, frac: float, text: str):
        """Thread-safe progress update via after()."""
        row = self._rows.get(task_id)
        if row:
            task = row._task
            row.after(0, lambda: row.update_progress(frac, text, task.status))

    def _on_task_complete(self, task_id: str, result):
        row = self._rows.get(task_id)
        if row:
            task = row._task
            final_text = "✓ Done" if result.success else f"✗ {result.error_message or 'Error'}"
            row.after(0, lambda: row.update_progress(
                1.0 if result.success else 0.0,
                final_text,
                task.status,
            ))
            row.after(0, lambda: self._btn_open.configure(state="normal"))
