"""
Settings View — theme picker, concurrency, output folder defaults, and FFmpeg manager.
"""
import os
import sys
import threading
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from gui import theme as T
from core.ffmpeg_manager import FFmpegManager


class SettingsView(ctk.CTkFrame):
    """Settings panel: themes, concurrency, output, and FFmpeg management."""

    def __init__(self, parent, on_theme_change=None, on_concurrency_change=None):
        super().__init__(parent, fg_color="transparent")
        self._on_theme_change = on_theme_change
        self._on_concurrency_change = on_concurrency_change
        self._ffmpeg = FFmpegManager()
        self._download_thread: Optional[threading.Thread] = None

        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)

        self._scroll = scroll
        self._build_header()
        self._build_theme_section()
        self._build_concurrency_section()
        self._build_output_section()
        self._build_ffmpeg_section()

    def _section_card(self, title: str) -> ctk.CTkFrame:
        """Create a titled card container."""
        card = ctk.CTkFrame(self._scroll, fg_color=T.c("bg_card"),
                            corner_radius=12, border_width=1,
                            border_color=T.c("border"))
        card.pack(fill="x", pady=8, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=title,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T.c("accent"),
                     anchor="w").grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        sep = ctk.CTkFrame(card, height=1, fg_color=T.c("border"))
        sep.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        return card

    def _build_header(self):
        ctk.CTkLabel(self._scroll, text="Settings",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=T.c("text_primary"),
                     anchor="w").pack(fill="x", padx=4, pady=(0, 12))

    def _build_theme_section(self):
        card = self._section_card("🎨  Appearance & Theme")

        themes = list(T.THEMES.keys())
        self._theme_var = tk.StringVar(value=T.current_name)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")

        for i, name in enumerate(themes):
            pal = T.THEMES[name]
            theme_btn = ctk.CTkFrame(inner,
                                      fg_color=pal["bg_card"],
                                      corner_radius=10,
                                      border_width=2,
                                      border_color=pal["accent"] if name == T.current_name else pal["border"])
            theme_btn.pack(side="left", padx=6, pady=4)
            theme_btn.bind("<Button-1>", lambda e, n=name: self._select_theme(n))

            # Color swatch row
            swatch_row = ctk.CTkFrame(theme_btn, fg_color="transparent")
            swatch_row.pack(padx=10, pady=(10, 4))
            for color_key in ("bg_primary", "accent", "success"):
                swatch = ctk.CTkFrame(swatch_row, width=18, height=18,
                                      fg_color=pal[color_key], corner_radius=4)
                swatch.pack(side="left", padx=2)
                swatch.bind("<Button-1>", lambda e, n=name: self._select_theme(n))

            lbl = ctk.CTkLabel(theme_btn, text=name,
                               font=ctk.CTkFont(size=12, weight="bold"),
                               text_color=pal["text_primary"])
            lbl.pack(padx=10, pady=(0, 10))
            lbl.bind("<Button-1>", lambda e, n=name: self._select_theme(n))

            # Store reference to update border on selection
            theme_btn._theme_name = name
            self._theme_cards = getattr(self, "_theme_cards", {})
            self._theme_cards[name] = theme_btn

    def _select_theme(self, name: str):
        import customtkinter as ctk
        T.apply_theme(name)
        ctk.set_appearance_mode(T.c("ctk_appearance"))
        if self._on_theme_change:
            self._on_theme_change(name)

    def _build_concurrency_section(self):
        card = self._section_card("⚡  Conversion Performance")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")

        import os
        cpu_count = os.cpu_count() or 4

        ctk.CTkLabel(inner, text="Parallel threads:",
                     text_color=T.c("text_secondary"),
                     font=ctk.CTkFont(size=13)).pack(side="left")

        self._threads_var = tk.IntVar(value=T.load_settings().get("threads", min(4, cpu_count)))
        slider = ctk.CTkSlider(inner, from_=1, to=cpu_count,
                               number_of_steps=cpu_count - 1,
                               variable=self._threads_var,
                               width=200,
                               fg_color=T.c("progress_track"),
                               progress_color=T.c("accent"),
                               button_color=T.c("accent"),
                               command=self._on_threads_change)
        slider.pack(side="left", padx=12)

        self._threads_label = ctk.CTkLabel(inner,
                                            text=str(self._threads_var.get()),
                                            font=ctk.CTkFont(size=13, weight="bold"),
                                            text_color=T.c("accent"))
        self._threads_label.pack(side="left")
        ctk.CTkLabel(inner, text=f"/ {cpu_count} cores",
                     text_color=T.c("text_muted"),
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=4)

    def _on_threads_change(self, val):
        n = int(val)
        self._threads_label.configure(text=str(n))
        T.save_settings({"threads": n})
        if self._on_concurrency_change:
            self._on_concurrency_change(n)

    def _build_output_section(self):
        card = self._section_card("📁  Default Output")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")

        saved_dir = T.load_settings().get("output_dir", "")
        self._output_dir_var = tk.StringVar(value=saved_dir or "Same folder as source file")

        entry = ctk.CTkEntry(inner, textvariable=self._output_dir_var,
                              width=300, height=34,
                              fg_color=T.c("bg_secondary"),
                              border_color=T.c("border"),
                              text_color=T.c("text_secondary"))
        entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(inner, text="Browse…", width=90, height=34,
                      fg_color=T.c("bg_secondary"),
                      hover_color=T.c("bg_hover"),
                      text_color=T.c("text_primary"),
                      corner_radius=6,
                      command=self._pick_default_output).pack(side="left")

        ctk.CTkButton(inner, text="Reset", width=70, height=34,
                      fg_color="transparent",
                      hover_color=T.c("bg_hover"),
                      text_color=T.c("text_muted"),
                      corner_radius=6,
                      command=self._reset_output_dir).pack(side="left", padx=4)

    def _pick_default_output(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Default output folder")
        if folder:
            self._output_dir_var.set(folder)
            T.save_settings({"output_dir": folder})

    def _reset_output_dir(self):
        self._output_dir_var.set("Same folder as source file")
        T.save_settings({"output_dir": ""})

    def _build_ffmpeg_section(self):
        card = self._section_card("🎬  FFmpeg Engine")
        self._ffmpeg_card = card

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        inner.grid_columnconfigure(1, weight=1)

        # Status badge
        ok, version_str, ffmpeg_path = self._ffmpeg.get_version_info()

        badge_color = T.c("badge_done") if ok else T.c("badge_error")
        badge_text_color = T.c("success") if ok else T.c("error")
        status_text = "Installed" if ok else "Not Found"

        self._ffmpeg_badge = ctk.CTkLabel(inner,
                                           text=f"  {status_text}  ",
                                           fg_color=badge_color,
                                           corner_radius=6,
                                           text_color=badge_text_color,
                                           font=ctk.CTkFont(size=12, weight="bold"))
        self._ffmpeg_badge.grid(row=0, column=0, padx=(0, 12), pady=4, sticky="w")

        self._ffmpeg_version_label = ctk.CTkLabel(inner,
                                                    text=version_str[:80] if version_str else "",
                                                    text_color=T.c("text_muted"),
                                                    font=ctk.CTkFont(size=11))
        self._ffmpeg_version_label.grid(row=0, column=1, sticky="w")

        self._ffmpeg_path_label = ctk.CTkLabel(inner,
                                                text=ffmpeg_path[:80] if ffmpeg_path else "",
                                                text_color=T.c("text_muted"),
                                                font=ctk.CTkFont(size=10))
        self._ffmpeg_path_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, sticky="w")

        self._ffmpeg_dl_btn = ctk.CTkButton(btn_row,
                                             text="⬇  Download Portable FFmpeg",
                                             fg_color=T.c("accent_dim"),
                                             hover_color=T.c("accent"),
                                             text_color=T.c("accent"),
                                             font=ctk.CTkFont(size=12),
                                             height=34, corner_radius=8,
                                             command=self._start_ffmpeg_download)
        self._ffmpeg_dl_btn.pack(side="left", padx=(0, 8))

        self._ffmpeg_progress_bar = ctk.CTkProgressBar(btn_row, width=200, height=8,
                                                         progress_color=T.c("accent"),
                                                         fg_color=T.c("progress_track"))
        self._ffmpeg_progress_bar.set(0)
        self._ffmpeg_progress_bar.pack(side="left")

        self._ffmpeg_progress_label = ctk.CTkLabel(btn_row, text="",
                                                    text_color=T.c("text_secondary"),
                                                    font=ctk.CTkFont(size=11))
        self._ffmpeg_progress_label.pack(side="left", padx=8)

    def _start_ffmpeg_download(self):
        if self._download_thread and self._download_thread.is_alive():
            return
        self._ffmpeg_dl_btn.configure(state="disabled", text="Downloading…")
        self._cancel_dl = threading.Event()

        self._download_thread = threading.Thread(
            target=self._do_ffmpeg_download,
            daemon=True
        )
        self._download_thread.start()

    def _do_ffmpeg_download(self):
        def progress_cb(frac: float, text: str):
            self._ffmpeg_progress_bar.after(
                0, lambda: self._ffmpeg_progress_bar.set(frac)
            )
            self._ffmpeg_progress_label.after(
                0, lambda: self._ffmpeg_progress_label.configure(text=text)
            )

        success, msg = self._ffmpeg.download_portable_ffmpeg(
            progress_callback=progress_cb,
            cancel_event=self._cancel_dl,
        )

        def finish():
            if success:
                ok2, ver2, path2 = self._ffmpeg.get_version_info()
                self._ffmpeg_badge.configure(
                    text="  Installed  ",
                    fg_color=T.c("badge_done"),
                    text_color=T.c("success"),
                )
                self._ffmpeg_version_label.configure(text=ver2[:80])
                self._ffmpeg_path_label.configure(text=path2[:80])
            self._ffmpeg_dl_btn.configure(state="normal", text="⬇  Download Portable FFmpeg")
            self._ffmpeg_progress_label.configure(text=msg[:60] if msg else "")

        self._ffmpeg_progress_bar.after(0, finish)
