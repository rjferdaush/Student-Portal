"""Exam Routine System - desktop app (CustomTkinter).

Run:  python app.py
Screens: Login/Register (student, teacher, admin), student dashboard,
         teacher dashboard, admin panel.
"""
import contextlib
import io

import customtkinter as ctk

import academic
import allocate_rooms
import auth
from db import get_connection
from screens_admin import AdminFrame
from screens_student import StudentFrame
from screens_teacher import TeacherFrame
from ui_kit import (ACCENT, ACCENT_HOVER, BAD, BG, BRAND, CARD, CARD_SOFT, GOOD, MUTED, PANEL,
                    TEXT, font)

# ---------- Login / Register ----------
class LoginFrame(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app, fg_color=BG, corner_radius=0)
        self.app = app
        self.role = "student"
        self.mode = "Login"
        self.grid_columnconfigure(0, weight=5, uniform="cols")
        self.grid_columnconfigure(1, weight=6, uniform="cols")
        self.grid_rowconfigure(0, weight=1)
        self.build_brand()
        self.build_form()
        self.refresh_labels()

    def build_brand(self):
        brand = ctk.CTkFrame(self, fg_color=BRAND, corner_radius=0)
        brand.grid(row=0, column=0, sticky="nsew")
        inner = ctk.CTkFrame(brand, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(inner, text="EXAM", font=font(52, True), text_color="#FFFFFF").pack(anchor="w")
        ctk.CTkLabel(inner, text="ROUTINE", font=font(52, True), text_color="#A5B4FC").pack(anchor="w")
        ctk.CTkLabel(inner, text="Smart exam scheduling for\nstudents and teachers.",
                     font=font(16), text_color="#E0E7FF", justify="left").pack(anchor="w", pady=(10, 28))
        for line in ("Your exam date, time, room and seat",
                     "Teachers see duty rooms and partners",
                     "No clash: one exam per student per day"):
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(anchor="w", pady=5)
            ctk.CTkFrame(row, fg_color="#A5B4FC", width=10, height=10, corner_radius=5).pack(
                side="left", padx=(0, 12))
            ctk.CTkLabel(row, text=line, font=font(14), text_color="#E0E7FF").pack(side="left")

    def build_form(self):
        side = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        side.grid(row=0, column=1, sticky="nsew")
        card = ctk.CTkFrame(side, fg_color=PANEL, corner_radius=20, width=420)
        card.place(relx=0.5, rely=0.5, anchor="center")
        pad = dict(padx=34, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        self.title = ctk.CTkLabel(card, text="", font=font(26, True), text_color=TEXT)
        self.title.grid(row=0, column=0, padx=34, pady=(30, 0), sticky="w")
        self.subtitle = ctk.CTkLabel(card, text="", font=font(13), text_color=MUTED)
        self.subtitle.grid(row=1, column=0, padx=34, pady=(2, 14), sticky="w")

        self.role_seg = ctk.CTkSegmentedButton(
            card, values=["Student", "Teacher", "Admin"], command=self.on_role, height=36,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            unselected_color=CARD, unselected_hover_color=CARD_SOFT, fg_color=CARD,
            font=font(13, True))
        self.role_seg.set("Student")
        self.role_seg.grid(row=2, column=0, pady=(0, 8), **pad)

        self.mode_seg = ctk.CTkSegmentedButton(
            card, values=["Login", "Register"], command=self.on_mode, height=32,
            selected_color=CARD_SOFT, selected_hover_color=CARD_SOFT,
            unselected_color=CARD, unselected_hover_color=CARD_SOFT, fg_color=CARD,
            font=font(12))
        self.mode_seg.set("Login")
        self.mode_seg.grid(row=3, column=0, pady=(0, 14), **pad)

        self.id_label = ctk.CTkLabel(card, text="", font=font(12, True), text_color=MUTED)
        self.id_label.grid(row=4, column=0, padx=34, sticky="w")
        self.id_entry = ctk.CTkEntry(card, height=44, corner_radius=10, fg_color=CARD,
                                     border_color=CARD_SOFT, text_color=TEXT)
        self.id_entry.grid(row=5, column=0, pady=(2, 10), **pad)

        ctk.CTkLabel(card, text="Password", font=font(12, True), text_color=MUTED).grid(
            row=6, column=0, padx=34, sticky="w")
        self.pw_entry = ctk.CTkEntry(card, height=44, corner_radius=10, show="*", fg_color=CARD,
                                     border_color=CARD_SOFT, text_color=TEXT)
        self.pw_entry.grid(row=7, column=0, pady=(2, 10), **pad)

        self.confirm_label = ctk.CTkLabel(card, text="Confirm password", font=font(12, True),
                                          text_color=MUTED)
        self.confirm_label.grid(row=8, column=0, padx=34, sticky="w")
        self.confirm_entry = ctk.CTkEntry(card, height=44, corner_radius=10, show="*", fg_color=CARD,
                                          border_color=CARD_SOFT, text_color=TEXT,
                                          placeholder_text="Type the password again")
        self.confirm_entry.grid(row=9, column=0, pady=(2, 10), **pad)

        self.show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(card, text="Show password", variable=self.show_var, command=self.toggle_show,
                        font=font(12), text_color=MUTED, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                        checkbox_width=18, checkbox_height=18).grid(row=10, column=0, pady=(0, 14), **pad)

        self.submit = ctk.CTkButton(card, text="", height=46, corner_radius=12, font=font(15, True),
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.on_submit)
        self.submit.grid(row=11, column=0, pady=(0, 8), **pad)

        self.message = ctk.CTkLabel(card, text="", font=font(13), wraplength=350, justify="left")
        self.message.grid(row=12, column=0, padx=34, pady=(0, 26), sticky="w")

        for w in (self.id_entry, self.pw_entry, self.confirm_entry):
            w.bind("<Return>", lambda e: self.on_submit())

    # ----- behaviour -----
    def on_role(self, value):
        self.role = value.lower()
        self.set_message("")
        self.refresh_labels()

    def on_mode(self, value):
        self.mode = value
        self.set_message("")
        self.refresh_labels()

    def toggle_show(self):
        ch = "" if self.show_var.get() else "*"
        self.pw_entry.configure(show=ch)
        self.confirm_entry.configure(show=ch)

    def set_message(self, text, good=False):
        self.message.configure(text=text, text_color=GOOD if good else BAD)

    def refresh_labels(self):
        register = self.mode == "Register"
        self.title.configure(text="Create account" if register else "Welcome back")
        hints = {
            "student": "Use your student ID from the university list.",
            "teacher": "Use the teacher ID given by the admin.",
            "admin": "First-time setup: choose an admin password." if register
                     else "Login with the admin password.",
        }
        self.subtitle.configure(text=hints[self.role])
        if self.role == "admin":
            self.id_label.grid_remove()
            self.id_entry.grid_remove()
        else:
            self.id_label.grid()
            self.id_entry.grid()
            self.id_label.configure(text="STUDENT ID" if self.role == "student" else "TEACHER ID")
            self.id_entry.configure(placeholder_text="Enter your ID")
        if register:
            self.confirm_label.grid()
            self.confirm_entry.grid()
            self.pw_entry.configure(placeholder_text=f"At least {auth.MIN_PASSWORD_LENGTH} characters")
        else:
            self.confirm_label.grid_remove()
            self.confirm_entry.grid_remove()
            self.pw_entry.configure(placeholder_text="Enter your password")
        self.submit.configure(text="Create account" if register else "Login")

    def on_submit(self):
        user_id = self.id_entry.get().strip()
        pw = self.pw_entry.get()
        confirm = self.confirm_entry.get()
        try:
            conn = get_connection()
        except Exception:
            self.set_message("Cannot connect to MySQL. Start MySQL in XAMPP and try again.")
            return
        try:
            if self.mode == "Register":
                ok, msg = auth.register(conn, self.role, user_id, pw, confirm)
                self.set_message(msg, good=ok)
                if ok:
                    self.mode_seg.set("Login")
                    self.mode = "Login"
                    self.refresh_labels()
                    self.confirm_entry.delete(0, "end")
                    self.pw_entry.delete(0, "end")
                    self.set_message(msg, good=True)
            else:
                ok, msg, name, uid = auth.login(conn, self.role, user_id, pw)
                if ok:
                    self.app.open_dashboard(self.role, uid, name)
                else:
                    self.set_message(msg)
        finally:
            conn.close()


# ---------- Error screen ----------
class ErrorFrame(ctk.CTkFrame):
    def __init__(self, app, message):
        super().__init__(app, fg_color=BG, corner_radius=0)
        box = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=20)
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(box, text="Cannot connect to MySQL", font=font(24, True),
                     text_color=BAD).pack(padx=50, pady=(34, 6))
        ctk.CTkLabel(box, text="1. Open XAMPP Control Panel and Start MySQL\n"
                               "2. Check the password in config.py\n3. Press Retry",
                     font=font(14), text_color=MUTED, justify="left").pack(padx=50, pady=6)
        ctk.CTkLabel(box, text=message[:200], font=font(11), text_color=MUTED,
                     wraplength=420).pack(padx=50, pady=6)
        ctk.CTkButton(box, text="Retry", height=42, width=160, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=app.start).pack(pady=(10, 34))


# ---------- Main window ----------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Exam Routine System")
        self.geometry("1120x720")
        self.minsize(1000, 660)
        self.configure(fg_color=BG)
        self.current = None
        self.start()

    def show(self, frame):
        if self.current is not None:
            self.current.destroy()
        self.current = frame
        frame.pack(fill="both", expand=True)

    def bootstrap(self):
        """Make sure the database and all tables exist (safe to run every time)."""
        import allocate_rooms
        import run_all
        with contextlib.redirect_stdout(io.StringIO()):
            conn = get_connection(with_database=False)
            try:
                run_all.run_schema(conn)
            finally:
                conn.close()
        conn = get_connection()
        try:
            conn.cursor().execute(allocate_rooms.CREATE_SEAT_PLAN)
            auth.ensure_tables(conn)
            academic.ensure_tables(conn)
        finally:
            conn.close()

    def start(self):
        try:
            self.bootstrap()
            self.show(LoginFrame(self))
        except Exception as e:
            self.show(ErrorFrame(self, str(e)))

    def open_dashboard(self, role, user_id, name):
        if role == "student":
            self.show(StudentFrame(self, user_id, name))
        elif role == "teacher":
            self.show(TeacherFrame(self, user_id, name))
        else:
            self.show(AdminFrame(self))

    def logout(self):
        self.show(LoginFrame(self))


if __name__ == "__main__":
    App().mainloop()
