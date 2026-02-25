# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Bottom status bar — Kitae themed."""

import customtkinter as ctk
from gui import theme as T


class StatusBar(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, height=38, corner_radius=0, fg_color=T.BG_PANEL,
                         border_color=T.BORDER, border_width=1)

        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Each metric: small label + value, stacked
        self.iteration_label = self._make_metric(col=0, label="FOLD", value="Idle")
        self.elapsed_label = self._make_metric(col=1, label="ELAPSED", value="00:00:00")
        self.cost_label = self._make_metric(col=2, label="COST", value="$0.00")
        self.status_label = self._make_metric(col=3, label="STATUS", value="\u2014",
                                               value_color=T.GOLD)

    def _make_metric(self, col: int, label: str, value: str,
                     value_color: str = T.TEXT_DIM) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=col, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(
            frame, text=label,
            font=("JetBrains Mono", 8),
            text_color=T.TEXT_MUTED,
            anchor="center",
        ).pack(side="top")

        val_lbl = ctk.CTkLabel(
            frame, text=value,
            font=("JetBrains Mono", 12, "bold"),
            text_color=value_color,
            anchor="center",
        )
        val_lbl.pack(side="top")
        return val_lbl

    def set_iteration(self, current: int, total: int):
        if total > 0:
            self.iteration_label.configure(text=f"{current}/{total}",
                                            text_color=T.TEXT)
        else:
            self.iteration_label.configure(text=f"{current}",
                                            text_color=T.TEXT)

    def set_elapsed(self, seconds: float):
        h = int(seconds) // 3600
        m = (int(seconds) % 3600) // 60
        s = int(seconds) % 60
        self.elapsed_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}",
                                      text_color=T.TEXT)

    def set_cost(self, usd: float):
        self.cost_label.configure(text=f"${usd:.2f}", text_color=T.TEXT)

    def set_status(self, text: str):
        color = T.GOLD
        if text == "Tempered":
            color = T.GREEN
        elif text == "Quenching":
            color = T.RED
        self.status_label.configure(text=text, text_color=color)

    def reset(self):
        self.iteration_label.configure(text="Idle", text_color=T.TEXT_DIM)
        self.elapsed_label.configure(text="00:00:00", text_color=T.TEXT_DIM)
        self.cost_label.configure(text="$0.00", text_color=T.TEXT_DIM)
        self.status_label.configure(text="\u2014", text_color=T.GOLD)
