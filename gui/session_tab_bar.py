# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Browser-style session tab bar."""

import customtkinter as ctk
from gui import theme as T
from gui.session import SessionStatus

MAX_TABS = 12


class SessionTabBar(ctk.CTkFrame):
    """Horizontal tab bar with status dots, names, close buttons, and a + button."""

    def __init__(self, parent, on_switch, on_new, on_close):
        super().__init__(parent, height=T.TAB_HEIGHT, fg_color=T.BG_PANEL, corner_radius=0)
        self._on_switch = on_switch
        self._on_new = on_new
        self._on_close = on_close

        self._tabs: dict[str, dict] = {}   # id -> {frame, dot, name_btn, close_btn}
        self._active_id: str = ""

        self.grid_columnconfigure(0, weight=1)

        # Scrollable inner frame for tabs
        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # New-tab button
        self._plus_btn = ctk.CTkButton(
            self, text="+", width=30, height=26,
            font=("JetBrains Mono", 14, "bold"),
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.TEXT_DIM, corner_radius=4,
            command=self._on_new,
        )
        self._plus_btn.pack(side="right", padx=(0, 6), pady=4)

    # ── Public API ────────────────────────────────────

    def add_tab(self, session_id: str, name: str, status: str = SessionStatus.IDLE):
        if session_id in self._tabs or len(self._tabs) >= MAX_TABS:
            return

        frame = ctk.CTkFrame(self._inner, fg_color="transparent")
        frame.pack(side="left", padx=(0, 1))

        # Status dot
        dot = ctk.CTkLabel(
            frame, text="\u25CF", width=10,
            font=("", 8), text_color=self._dot_color(status),
        )
        dot.pack(side="left", padx=(6, 2))

        # Name button
        name_btn = ctk.CTkButton(
            frame, text=name, height=26,
            font=("JetBrains Mono", 11),
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.TEXT_MUTED, corner_radius=4,
            command=lambda sid=session_id: self._on_switch(sid),
        )
        name_btn.pack(side="left")

        # Close button
        close_btn = ctk.CTkButton(
            frame, text="\u00d7", width=20, height=20,
            font=("JetBrains Mono", 12),
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.TEXT_MUTED, corner_radius=4,
            command=lambda sid=session_id: self._on_close(sid),
        )
        close_btn.pack(side="left", padx=(0, 4))

        self._tabs[session_id] = {
            "frame": frame, "dot": dot,
            "name_btn": name_btn, "close_btn": close_btn,
        }
        self._update_plus_btn()

    def remove_tab(self, session_id: str):
        tab = self._tabs.pop(session_id, None)
        if tab:
            tab["frame"].destroy()
        self._update_plus_btn()

    def set_active(self, session_id: str):
        self._active_id = session_id
        for sid, tab in self._tabs.items():
            if sid == session_id:
                tab["frame"].configure(fg_color=T.BG_ELEVATED)
                tab["name_btn"].configure(text_color=T.SAKURA_BRIGHT)
            else:
                tab["frame"].configure(fg_color="transparent")
                tab["name_btn"].configure(text_color=T.TEXT_MUTED)

    def update_tab(self, session_id: str, status: str = None, name: str = None):
        tab = self._tabs.get(session_id)
        if not tab:
            return
        if status is not None:
            tab["dot"].configure(text_color=self._dot_color(status))
        if name is not None:
            tab["name_btn"].configure(text=name)

    def tab_ids(self) -> list[str]:
        """Return tab IDs in display order."""
        return list(self._tabs.keys())

    # ── Private ───────────────────────────────────────

    def _dot_color(self, status: str) -> str:
        if status == SessionStatus.RUNNING:
            return T.TAB_DOT_RUNNING
        elif status == SessionStatus.COMPLETE:
            return T.TAB_DOT_COMPLETE
        elif status == SessionStatus.STOPPING:
            return T.RED
        return T.TAB_DOT_IDLE

    def _update_plus_btn(self):
        if len(self._tabs) >= MAX_TABS:
            self._plus_btn.configure(state="disabled", text_color=T.TEXT_FAINT)
        else:
            self._plus_btn.configure(state="normal", text_color=T.TEXT_DIM)
