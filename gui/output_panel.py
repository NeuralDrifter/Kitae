"""Center panel — tabbed agent output with Kitae theme."""

import customtkinter as ctk
from gui import theme as T


WELCOME_TEXT = """\




                          \u2692  K I T A E  \u2692

                    Forge. Fold. Refine. Repeat.


              Select your agents, choose a mode,
              write your prompt, and hit FORGE.

              Output from each agent will stream
              here in real-time.

"""


class OutputPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T.BG_DARK, corner_radius=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Tab bar ───────────────────────────────────
        tab_container = ctk.CTkFrame(self, fg_color=T.BG_PANEL, corner_radius=0, height=38)
        tab_container.grid(row=0, column=0, sticky="ew")
        tab_container.grid_columnconfigure(0, weight=1)

        self._tab_frame = ctk.CTkFrame(tab_container, fg_color="transparent")
        self._tab_frame.pack(side="left", padx=6, pady=0)

        self._textboxes: dict[str, ctk.CTkTextbox] = {}
        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        self._underlines: dict[str, ctk.CTkFrame] = {}
        self._active_tab: str = ""

        self._create_tab("All")
        self._switch_tab("All")

        # Show welcome message
        self._show_welcome()

    def ensure_tab(self, agent_name: str):
        if agent_name not in self._textboxes:
            self._create_tab(agent_name)

    def append(self, agent_name: str, text: str):
        self._append_to("All", text)
        if agent_name and agent_name != "loop":
            self.ensure_tab(agent_name)
            self._append_to(agent_name, text)

    def clear_all(self):
        for tb in self._textboxes.values():
            tb.configure(state="normal")
            tb.delete("1.0", "end")
            tb.configure(state="disabled")

    def _show_welcome(self):
        tb = self._textboxes.get("All")
        if tb:
            tb.configure(state="normal")
            tb.insert("end", WELCOME_TEXT)
            tb.configure(state="disabled")

    def _create_tab(self, name: str):
        # Tab button container (button + underline)
        tab_wrapper = ctk.CTkFrame(self._tab_frame, fg_color="transparent")
        tab_wrapper.pack(side="left", padx=(0, 2))

        btn = ctk.CTkButton(
            tab_wrapper,
            text=name.capitalize(),
            width=80, height=30,
            corner_radius=4,
            font=("JetBrains Mono", 11),
            fg_color="transparent",
            hover_color=T.BG_HOVER,
            text_color=T.TEXT_MUTED,
            border_width=0,
            command=lambda n=name: self._switch_tab(n),
        )
        btn.pack(side="top")

        # Underline indicator
        underline = ctk.CTkFrame(tab_wrapper, height=2, fg_color="transparent",
                                  corner_radius=1)
        underline.pack(side="top", fill="x", padx=8)

        self._tab_buttons[name] = btn
        self._underlines[name] = underline

        tb = ctk.CTkTextbox(
            self,
            font=("JetBrains Mono", 12),
            wrap="word",
            state="disabled",
            activate_scrollbars=True,
            fg_color=T.BG_INPUT,
            text_color=T.TEXT,
            scrollbar_button_color=T.SAKURA_DIM,
            scrollbar_button_hover_color=T.SAKURA,
            border_color=T.BORDER,
            border_width=1,
            corner_radius=6,
        )
        self._textboxes[name] = tb

    def _switch_tab(self, name: str):
        if self._active_tab and self._active_tab in self._textboxes:
            self._textboxes[self._active_tab].grid_forget()

        self._active_tab = name
        self._textboxes[name].grid(row=1, column=0, sticky="nsew", padx=4, pady=(4, 4))

        for n, btn in self._tab_buttons.items():
            if n == name:
                btn.configure(text_color=T.SAKURA_BRIGHT, fg_color="transparent")
                self._underlines[n].configure(fg_color=T.SAKURA)
            else:
                btn.configure(text_color=T.TEXT_MUTED, fg_color="transparent")
                self._underlines[n].configure(fg_color="transparent")

    def _append_to(self, name: str, text: str):
        tb = self._textboxes.get(name)
        if not tb:
            return
        tb.configure(state="normal")
        tb.insert("end", text)
        tb.see("end")
        tb.configure(state="disabled")
