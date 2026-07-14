"""Touch calculator UI backed by the bounded parser."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .calculator import CalculationError, calculate, format_result
from .common_ui import (
    ACCENT,
    ACCENT_CONTAINER,
    ACCENT_HOVER,
    ERROR,
    FIELD,
    OUTLINE,
    SURFACE,
    TEXT,
    TouchApplication,
)
from .localization import AppsI18n
from msys_sdk.ui_fonts import font_spec


class CalculatorApplication(TouchApplication):
    BUTTONS = (
        ("C", "clear"), ("⌫", "back"), ("(", "("), (")", ")"),
        ("7", "7"), ("8", "8"), ("9", "9"), ("÷", "/"),
        ("4", "4"), ("5", "5"), ("6", "6"), ("×", "*"),
        ("1", "1"), ("2", "2"), ("3", "3"), ("−", "-"),
        ("0", "0"), (".", "."), ("%", "%"), ("+", "+"),
        ("±", "negate"), ("//", "//"), ("xʸ", "**"), ("=", "equals"),
    )

    def __init__(self) -> None:
        i18n = AppsI18n()
        super().__init__(
            title=i18n("calculator.window_title"),
            identity="org.msys.apps.calculator",
            icon_name="calculator.ppm",
            i18n=i18n,
        )
        self.expression = tk.StringVar()
        self.just_calculated = False
        short_screen = self.root.winfo_screenheight() <= 360
        self.header(self.i18n("calculator.title"))

        display_frame = ttk.Frame(
            self.root,
            padding=(8, 1, 8, 4 if short_screen else 7),
        )
        display_frame.pack(fill="x")
        self.display = tk.Entry(
            display_frame,
            textvariable=self.expression,
            bg=FIELD,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#285f91",
            relief="flat",
            highlightthickness=1,
            highlightbackground=OUTLINE,
            highlightcolor=ACCENT,
            justify="right",
            font=font_spec(
                self.root,
                17 if short_screen else (20 if self.compact else 26),
                "bold",
            ),
        )
        self.display.pack(fill="x", ipady=5 if short_screen else 9)
        self.display.bind("<Return>", lambda _event: self.equals())
        self.display.bind("<Escape>", lambda _event: self.clear())

        keypad = ttk.Frame(
            self.root,
            padding=(5 if short_screen else 7, 0, 5 if short_screen else 7, 5 if short_screen else 8),
        )
        keypad.pack(fill="both", expand=True)
        for row in range(6):
            keypad.rowconfigure(row, weight=1, uniform="key")
        for column in range(4):
            keypad.columnconfigure(column, weight=1, uniform="key")
        for index, (label, action) in enumerate(self.BUTTONS):
            row, column = divmod(index, 4)
            is_equals = action == "equals"
            is_clear = action == "clear"
            is_operator = action in {
                "+", "-", "*", "/", "//", "%", "**", "negate",
            }
            background = (
                ACCENT
                if is_equals
                else "#ffdad6"
                if is_clear
                else ACCENT_CONTAINER
                if is_operator
                else SURFACE
            )
            foreground = "#ffffff" if is_equals else ERROR if is_clear else TEXT
            button = tk.Button(
                keypad,
                text=label,
                command=lambda selected=action: self.press(selected),
                bg=background,
                fg=foreground,
                activebackground=ACCENT_HOVER if is_equals else "#d4dcec",
                activeforeground="#ffffff" if is_equals else TEXT,
                relief="flat",
                bd=0,
                highlightthickness=0,
                font=font_spec(
                    self.root,
                    12 if short_screen else (14 if self.compact else 17),
                    "bold",
                ),
                takefocus=True,
            )
            gap = 2 if short_screen else 3
            button.grid(row=row, column=column, sticky="nsew", padx=gap, pady=gap)
        self.display.focus_set()
        self.activate_lifecycle()

    def press(self, action: str) -> None:
        if action == "clear":
            self.clear()
        elif action == "back":
            self.expression.set(self.expression.get()[:-1])
            self.just_calculated = False
        elif action == "equals":
            self.equals()
        elif action == "negate":
            current = self.expression.get().strip()
            self.expression.set(f"-({current})" if current else "-")
            self.just_calculated = False
        else:
            if self.just_calculated and action not in {"+", "-", "*", "/", "//", "%", "**"}:
                self.expression.set("")
            self.expression.set(self.expression.get() + action)
            self.just_calculated = False
        self.display.icursor("end")
        self.display.xview_moveto(1.0)

    def clear(self) -> None:
        self.expression.set("")
        self.just_calculated = False
        self.set_status(self.i18n("common.ready"))

    def equals(self) -> None:
        source = self.expression.get()
        try:
            result = format_result(calculate(source))
        except CalculationError:
            self.set_status(self.i18n("calculator.invalid"), error=True)
            self.root.bell()
            return
        self.expression.set(result)
        self.just_calculated = True
        self.set_status(self.i18n("calculator.result"))
        self.display.selection_range(0, "end")
        self.display.icursor("end")
        self.display.xview_moveto(1.0)


def main() -> int:
    return CalculatorApplication().run()
