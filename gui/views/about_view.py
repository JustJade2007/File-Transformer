"""
About View — supported format matrix and app info.
"""
import tkinter as tk
import customtkinter as ctk
from core.registry import FormatRegistry
from gui import theme as T

APP_VERSION = "1.0.0"


class AboutView(ctk.CTkFrame):
    """Displays app info, version, and a full supported format conversion matrix."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._registry = FormatRegistry()
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(scroll, fg_color=T.c("bg_card"),
                               corner_radius=12, border_width=1,
                               border_color=T.c("border"))
        header.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(header, text="File Transformer",
                     font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=T.c("text_primary")).pack(pady=(20, 2))

        ctk.CTkLabel(header, text=f"v{APP_VERSION}  |  Local • Private • No Limits",
                     font=ctk.CTkFont(size=13),
                     text_color=T.c("accent")).pack(pady=(0, 4))

        ctk.CTkLabel(header, text="Convert files locally without internet. No uploads. No subscriptions.",
                     font=ctk.CTkFont(size=12),
                     text_color=T.c("text_secondary")).pack(pady=(0, 20))

        # Format matrix by category
        ctk.CTkLabel(scroll, text="Supported Conversions",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=T.c("text_primary"),
                     anchor="w").pack(fill="x", padx=4, pady=(8, 4))

        all_inputs_by_cat = self._registry.get_all_supported_inputs()

        for category, input_exts in all_inputs_by_cat.items():
            card = ctk.CTkFrame(scroll, fg_color=T.c("bg_card"),
                                corner_radius=10, border_width=1,
                                border_color=T.c("border"))
            card.pack(fill="x", pady=4, padx=4)

            ctk.CTkLabel(card, text=f"  {category}",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=T.c("accent"),
                         anchor="w").pack(fill="x", padx=12, pady=(12, 4))

            for ext in sorted(set(input_exts)):
                valid = self._registry.get_valid_targets(ext)
                all_targets = []
                for targets in valid.values():
                    all_targets.extend(targets)
                if not all_targets:
                    continue

                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=2)

                ctk.CTkLabel(row,
                             text=f".{ext}",
                             width=60, anchor="e",
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color=T.c("text_primary")).pack(side="left")

                ctk.CTkLabel(row, text="→",
                             font=ctk.CTkFont(size=12),
                             text_color=T.c("text_muted")).pack(side="left", padx=8)

                targets_str = "  ".join(f".{t}" for t in sorted(set(all_targets)))
                ctk.CTkLabel(row, text=targets_str,
                             font=ctk.CTkFont(size=11),
                             text_color=T.c("text_secondary"),
                             anchor="w").pack(side="left")

            ctk.CTkFrame(card, height=1, fg_color=T.c("border")).pack(
                fill="x", padx=12, pady=(8, 12))

        # Credits footer
        footer = ctk.CTkFrame(scroll, fg_color="transparent")
        footer.pack(fill="x", padx=4, pady=(12, 0))

        ctk.CTkLabel(footer, text="Built with: Python 3 • CustomTkinter • Pillow • PyPDF • FontTools • FFmpeg",
                     font=ctk.CTkFont(size=11),
                     text_color=T.c("text_muted")).pack()
        ctk.CTkLabel(footer, text="License: MIT  |  Fully local, fully private.",
                     font=ctk.CTkFont(size=11),
                     text_color=T.c("text_muted")).pack(pady=(2, 16))
