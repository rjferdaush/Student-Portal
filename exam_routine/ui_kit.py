"""Shared look, small widgets and the dashboard base used by all screens."""
import io
import queue
from datetime import date

import customtkinter as ctk

import academic

# ---------- Look and feel ----------
BG = "#0B1020"
PANEL = "#121933"
CARD = "#1A2347"
CARD_SOFT = "#222C57"
ACCENT = "#6366F1"
ACCENT_HOVER = "#4F52D9"
BRAND = "#3730A3"
TEXT = "#F3F4F6"
MUTED = "#9AA4C7"
GOOD = "#22C55E"
BAD = "#F87171"
CHIP = "#2B3768"
CHIP_TEXT = "#C7D2FE"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def font(size=14, bold=False):
    return ctk.CTkFont(size=size, weight="bold" if bold else "normal")


# ---------- Small building blocks ----------
def stat_card(parent, title, value, color=ACCENT):
    box = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14)
    ctk.CTkFrame(box, fg_color=color, width=5, height=10, corner_radius=3).pack(
        side="left", fill="y", padx=(10, 0), pady=14)
    inner = ctk.CTkFrame(box, fg_color="transparent")
    inner.pack(side="left", padx=14, pady=12)
    value_label = ctk.CTkLabel(inner, text=str(value), font=font(22, True), text_color=TEXT)
    value_label.pack(anchor="w")
    ctk.CTkLabel(inner, text=title, font=font(12), text_color=MUTED).pack(anchor="w")
    box.value_label = value_label
    return box


def chip(parent, text, color=CHIP, text_color=CHIP_TEXT):
    return ctk.CTkLabel(parent, text=text, fg_color=color, text_color=text_color,
                        corner_radius=8, height=28, font=font(12, True), padx=10)


def date_block(parent, d, done=False):
    block = ctk.CTkFrame(parent, fg_color=(CARD_SOFT if done else BRAND),
                         corner_radius=12, width=86, height=86)
    block.grid_propagate(False)
    block.pack_propagate(False)
    color = MUTED if done else TEXT
    ctk.CTkLabel(block, text=d.strftime("%d"), font=font(28, True), text_color=color).pack(pady=(8, 0))
    ctk.CTkLabel(block, text=d.strftime("%b").upper(), font=font(12, True), text_color=color).pack()
    ctk.CTkLabel(block, text=d.strftime("%a"), font=font(11), text_color=MUTED).pack()
    return block


# ---------- Dashboard base ----------
class Dashboard(ctk.CTkFrame):
    def __init__(self, app, role_label, name):
        super().__init__(app, fg_color=BG, corner_radius=0)
        self.app = app
        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=64)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(top, text="Exam Routine", font=font(18, True), text_color=TEXT).pack(
            side="left", padx=(26, 12))
        ctk.CTkLabel(top, text=role_label.upper(), fg_color=ACCENT, text_color="#FFFFFF",
                     corner_radius=8, width=84, height=26, font=font(11, True)).pack(side="left")
        ctk.CTkButton(top, text="Logout", width=90, height=34, corner_radius=10, fg_color=CARD,
                      hover_color=CARD_SOFT, text_color=TEXT, command=app.logout).pack(
            side="right", padx=26)
        ctk.CTkLabel(top, text=name, font=font(14, True), text_color=MUTED).pack(side="right")
        self.body = ctk.CTkFrame(self, fg_color=BG)
        self.body.pack(fill="both", expand=True, padx=30, pady=22)

    def header(self, title, subtitle, refresh_cmd=None):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x")
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text=title, font=font(28, True), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(left, text=subtitle, font=font(13), text_color=MUTED, justify="left").pack(anchor="w")
        if refresh_cmd:
            ctk.CTkButton(row, text="Refresh", width=96, height=36, corner_radius=10,
                          fg_color=CARD, hover_color=CARD_SOFT, text_color=TEXT,
                          command=refresh_cmd).pack(side="right")

    def stats_row(self, items):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(18, 10))
        for i, (title, value, color) in enumerate(items):
            row.grid_columnconfigure(i, weight=1, uniform="stat")
            stat_card(row, title, value, color).grid(row=0, column=i, sticky="ew",
                                                     padx=(0 if i == 0 else 8, 0))

    def make_tabs(self, names):
        tabs = ctk.CTkTabview(self.body, fg_color=PANEL, corner_radius=16,
                              segmented_button_selected_color=ACCENT,
                              segmented_button_selected_hover_color=ACCENT_HOVER,
                              segmented_button_unselected_color=CARD,
                              segmented_button_unselected_hover_color=CARD_SOFT)
        tabs.pack(fill="both", expand=True, pady=(4, 0))
        out = {}
        for n in names:
            tabs.add(n)
            out[n] = tabs.tab(n)
        return tabs, out

    def scroll(self, parent):
        box = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        box.pack(fill="both", expand=True)
        return box

    def empty_state(self, parent, text):
        box = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=16)
        box.pack(fill="x", pady=10)
        ctk.CTkLabel(box, text=text, font=font(15), text_color=MUTED, wraplength=640,
                     justify="center").pack(padx=30, pady=46)


def status_for(d, next_date):
    today = date.today()
    if d < today:
        return "DONE"
    return "NEXT" if d == next_date else ""




class QueueWriter(io.TextIOBase):
    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(s)
        return len(s)

    def flush(self):
        pass


DONE = object()




# ---------- Weekly timetable widget ----------
FULL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CELL_COLORS = ["#3B4A9E", "#2F6F6B", "#7A3E8E", "#8A5A2B", "#2C6A94", "#8B3A52", "#4F6B2E", "#5B4B9A"]


def color_for(key):
    return CELL_COLORS[sum(ord(c) for c in key) % len(CELL_COLORS)]


class TimetableGrid(ctk.CTkFrame):
    """items = [{'day', 'period', 'code', ...}]. lines_fn(item) -> list of text lines."""

    def __init__(self, parent, periods, days, items, lines_fn):
        super().__init__(parent, fg_color="transparent")
        periods = list(periods)
        known = {p[0] for p in periods}
        for it in items:
            if it["period"] not in known:
                periods.append((it["period"], it["start"], it["end"]))
                known.add(it["period"])
        periods.sort()
        used_days = [d for d in days]
        for it in items:
            if it["day"] not in used_days:
                used_days.append(it["day"])
        order = [d for d in academic.WEEK_ORDER if d in used_days]
        by = {(it["day"], it["period"]): it for it in items}

        self.grid_columnconfigure(0, minsize=96)
        for c, d in enumerate(order, start=1):
            self.grid_columnconfigure(c, weight=1, uniform="tt")
            ctk.CTkLabel(self, text=FULL_DAYS[d], font=font(13, True), text_color=CHIP_TEXT,
                         fg_color=CARD, corner_radius=8, height=32).grid(
                row=0, column=c, sticky="ew", padx=3, pady=(0, 4))
        for r, (no, start, end) in enumerate(periods, start=1):
            lab = ctk.CTkFrame(self, fg_color="transparent")
            lab.grid(row=r, column=0, sticky="nsew", padx=(0, 4), pady=3)
            ctk.CTkLabel(lab, text=f"Period {no}", font=font(12, True), text_color=TEXT).pack(
                anchor="w", pady=(10, 0))
            ctk.CTkLabel(lab, text=f"{start}-{end}", font=font(11), text_color=MUTED).pack(anchor="w")
            for c, d in enumerate(order, start=1):
                it = by.get((d, no))
                if it:
                    cell = ctk.CTkFrame(self, fg_color=color_for(it["code"]), corner_radius=10, height=92)
                    cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
                    cell.pack_propagate(False)
                    for i, text in enumerate(lines_fn(it)):
                        ctk.CTkLabel(cell, text=text, font=font(13 if i == 0 else 11, i == 0),
                                     text_color="#FFFFFF" if i == 0 else "#E5E7EB").pack(
                            anchor="w", padx=10, pady=(7 if i == 0 else 1, 0))
                else:
                    ctk.CTkFrame(self, fg_color="#141B3A", corner_radius=10, height=92).grid(
                        row=r, column=c, sticky="nsew", padx=3, pady=3)
