"""
Main CustomTkinter application window.
Houses the sidebar navigation and hosts Queue, Settings, and About views.
"""
import os
import sys
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from gui import theme as T
from gui.views.queue_view import QueueView
from gui.views.settings_view import SettingsView
from gui.views.about_view import AboutView
from core.engine import ConversionEngine


class WelcomeDialog(ctk.CTkToplevel):
    """First-launch theme selection dialog."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Welcome to File Transformer")
        self.geometry("540x380")
        self.resizable(False, False)
        self.grab_set()
        self.chosen_theme: Optional[str] = None
        self.configure(fg_color=T.c("bg_primary"))

        ctk.CTkLabel(self, text="Welcome!",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=T.c("text_primary")).pack(pady=(30, 4))
        ctk.CTkLabel(self, text="Choose your preferred interface theme to get started.",
                     font=ctk.CTkFont(size=13),
                     text_color=T.c("text_secondary")).pack(pady=(0, 20))

        card_row = ctk.CTkFrame(self, fg_color="transparent")
        card_row.pack()

        for name, pal in T.THEMES.items():
            card = ctk.CTkFrame(card_row,
                                fg_color=pal["bg_card"],
                                corner_radius=12,
                                border_width=2,
                                border_color=pal["accent"],
                                cursor="hand2")
            card.pack(side="left", padx=8)

            swatch_row = ctk.CTkFrame(card, fg_color="transparent")
            swatch_row.pack(padx=14, pady=(14, 6))
            for key in ("bg_primary", "accent", "success", "error"):
                s = ctk.CTkFrame(swatch_row, width=20, height=20,
                                 fg_color=pal[key], corner_radius=4)
                s.pack(side="left", padx=2)

            ctk.CTkLabel(card, text=name,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=pal["text_primary"]).pack(padx=14, pady=(0, 4))

            btn = ctk.CTkButton(card, text="Select",
                                fg_color=pal["accent"],
                                hover_color=pal["accent_hover"],
                                text_color="#ffffff",
                                font=ctk.CTkFont(size=12),
                                corner_radius=8,
                                height=30,
                                command=lambda n=name: self._pick(n))
            btn.pack(padx=14, pady=(0, 14))

        ctk.CTkLabel(self, text="You can change this anytime in Settings.",
                     font=ctk.CTkFont(size=11),
                     text_color=T.c("text_muted")).pack(pady=(18, 0))

    def _pick(self, name: str):
        self.chosen_theme = name
        self.destroy()


class FileTransformerApp(ctk.CTk):
    """Main application window."""

    NAV_ITEMS = [
        ("🔀", "Convert", "queue"),
        ("⚙", "Settings", "settings"),
        ("ℹ", "About", "about"),
    ]

    def __init__(self):
        # Load saved theme before creating the window
        saved_theme = T.get_saved_theme()
        is_first_launch = saved_theme == T.DEFAULT_THEME and not os.path.exists(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        )
        T.apply_theme(saved_theme)
        ctk.set_appearance_mode(T.c("ctk_appearance"))
        ctk.set_default_color_theme("blue")

        super().__init__()
        self.title("File Transformer")
        self.geometry("1100x700")
        self.minsize(820, 580)
        self.configure(fg_color=T.c("bg_primary"))

        self._engine = ConversionEngine(
            max_workers=T.load_settings().get("threads", 4)
        )

        self._current_view_name = "queue"
        self._views = {}
        self._nav_buttons = {}

        self._build_layout()

        # First-launch welcome dialog
        if is_first_launch:
            self.after(200, self._show_welcome)

    def _build_layout(self):
        """Build sidebar + content area."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self,
                               width=72,
                               fg_color=T.c("bg_secondary"),
                               corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(10, weight=1)

        # App logo area
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent", height=70)
        logo_frame.grid(row=0, column=0, pady=(12, 8), padx=8, sticky="ew")
        logo_frame.grid_propagate(False)

        logo_inner = ctk.CTkFrame(logo_frame,
                                   fg_color=T.c("accent_dim"),
                                   corner_radius=10,
                                   width=50, height=50)
        logo_inner.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(logo_inner, text="⇄",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=T.c("accent")).place(relx=0.5, rely=0.5, anchor="center")

        # Nav buttons
        for i, (icon, label, view_id) in enumerate(self.NAV_ITEMS):
            btn = ctk.CTkButton(
                sidebar,
                text=f"{icon}\n{label}",
                width=56,
                height=56,
                font=ctk.CTkFont(size=10),
                fg_color=T.c("accent_dim") if view_id == "queue" else "transparent",
                hover_color=T.c("bg_hover"),
                text_color=T.c("accent") if view_id == "queue" else T.c("text_secondary"),
                corner_radius=10,
                command=lambda v=view_id: self._navigate(v),
            )
            btn.grid(row=i + 1, column=0, padx=8, pady=4)
            self._nav_buttons[view_id] = btn

        # ── Content area ─────────────────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color=T.c("bg_primary"), corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self._content = content

        # Build all views
        self._views["queue"] = QueueView(content, self._engine)
        self._views["settings"] = SettingsView(
            content,
            on_theme_change=self._on_theme_change,
            on_concurrency_change=self._on_concurrency_change,
        )
        self._views["about"] = AboutView(content)

        # Show initial view
        self._views["queue"].grid(row=0, column=0, sticky="nsew")

    def _navigate(self, view_id: str):
        """Switch between views."""
        if view_id == self._current_view_name:
            return

        # Hide current
        self._views[self._current_view_name].grid_forget()

        # Update nav button styles
        for vid, btn in self._nav_buttons.items():
            if vid == view_id:
                btn.configure(fg_color=T.c("accent_dim"), text_color=T.c("accent"))
            else:
                btn.configure(fg_color="transparent", text_color=T.c("text_secondary"))

        # Show new
        self._views[view_id].grid(row=0, column=0, sticky="nsew")
        self._current_view_name = view_id

    def _show_welcome(self):
        dialog = WelcomeDialog(self)
        self.wait_window(dialog)
        if dialog.chosen_theme:
            T.apply_theme(dialog.chosen_theme)
            T.save_settings({"theme": dialog.chosen_theme})
            ctk.set_appearance_mode(T.c("ctk_appearance"))

    def _on_theme_change(self, name: str):
        # Theme is already applied by settings view — just update title bar appearance
        ctk.set_appearance_mode(T.c("ctk_appearance"))

    def _on_concurrency_change(self, n: int):
        self._engine.set_max_workers(n)

    def on_closing(self):
        self._engine.shutdown(wait=False)
        self.destroy()


def run_gui():
    app = FileTransformerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
