"""Student dashboard: exam routine, class routine, courses and marks."""
from collections import defaultdict
from datetime import date

import customtkinter as ctk

import academic
import queries
from db import get_connection
from ui_kit import (ACCENT, BAD, BRAND, CARD, CARD_SOFT, CHIP_TEXT, GOOD, MUTED, TEXT, Dashboard,
                    TimetableGrid, chip, date_block, font, status_for)


class StudentFrame(Dashboard):
    def __init__(self, app, student_id, name):
        super().__init__(app, "Student", name)
        self.student_id = student_id
        self.name = name
        self.render()

    # ---------------------------------------------------------------- data
    def load(self):
        conn = get_connection()
        try:
            d = dict(info=queries.student_info(conn, self.student_id),
                     exams=queries.student_exams(conn, self.student_id),
                     sem=academic.active_semester(conn),
                     settings=academic.get_settings(conn))
            sid = d["sem"]["id"] if d["sem"] else 0
            d["courses"] = academic.student_courses(conn, self.student_id, sid)
            d["timetable"] = academic.student_timetable(conn, self.student_id, sid) if sid else []
            d["marks"] = academic.student_marks(conn, self.student_id, sid) if sid else {}
        finally:
            conn.close()
        return d

    # -------------------------------------------------------------- screen
    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        d = self.load()
        info, exams, sem = d["info"], d["exams"], d["sem"]
        sub = (f"ID {self.student_id}   |   {info['dept']}   |   Section {info['section']}"
               f"   |   Intake {info['intake']}")
        sub += ("\nSemester: " + academic.semester_text(sem)) if sem else "\nNo active semester yet"
        self.header(f"Hello, {self.name}", sub, self.render)

        upcoming = [e["date"] for e in exams if e["date"] >= date.today()]
        next_date = min(upcoming) if upcoming else None
        self.stats_row([
            ("Courses", len(d["courses"]), ACCENT),
            ("Exams", len(exams), GOOD),
            ("Next exam", next_date.strftime("%d %b %Y") if next_date else "-", "#F59E0B"),
            ("Classes per week", len(d["timetable"]), "#38BDF8"),
        ])
        _, tabs = self.make_tabs(["Exam routine", "Class routine", "My courses", "Marks"])
        self.exam_tab(tabs["Exam routine"], exams, next_date)
        self.class_tab(tabs["Class routine"], d)
        self.courses_tab(tabs["My courses"], d)
        self.marks_tab(tabs["Marks"], d)

    # ---------------------------------------------------------------- tabs
    def exam_tab(self, tab, exams, next_date):
        lst = self.scroll(tab)
        if not exams:
            self.empty_state(lst, "Your exam routine is not published yet.\n"
                                  "Please check again after the admin generates the routine.")
            return
        for e in exams:
            status = status_for(e["date"], next_date)
            done = status == "DONE"
            item = ctk.CTkFrame(lst, fg_color=CARD, corner_radius=14)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            date_block(item, e["date"], done).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            top = ctk.CTkFrame(mid, fg_color="transparent")
            top.pack(anchor="w")
            ctk.CTkLabel(top, text=e["code"], font=font(20, True),
                         text_color=MUTED if done else TEXT).pack(side="left")
            if status:
                chip(top, status, GOOD if status == "NEXT" else CARD_SOFT,
                     "#052E16" if status == "NEXT" else MUTED).pack(side="left", padx=10)
            ctk.CTkLabel(mid, text=e["course"], font=font(14), text_color=MUTED).pack(anchor="w")
            ctk.CTkLabel(mid, text=f"{e['start']} - {e['end']}", font=font(13, True),
                         text_color=CHIP_TEXT).pack(anchor="w", pady=(4, 0))
            right = ctk.CTkFrame(item, fg_color="transparent")
            right.grid(row=0, column=2, padx=18)
            chip(right, f"Room {e['building']}-{e['room']}").pack(pady=3, anchor="e")
            chip(right, f"Seat {e['seat']}", ACCENT, "#FFFFFF").pack(pady=3, anchor="e")

    def class_tab(self, tab, d):
        box = self.scroll(tab)
        if not d["timetable"]:
            self.empty_state(box, "Your class routine is not published yet.\n"
                                  "The admin will publish it after assigning teachers.")
            return
        s = d["settings"]
        TimetableGrid(box, academic.class_periods(s), academic.parse_days(s["class_days"]),
                      d["timetable"],
                      lambda it: [it["code"], it["teacher"], f"Room {it['room']}"]).pack(
            fill="x", padx=4, pady=4)

    def courses_tab(self, tab, d):
        lst = self.scroll(tab)
        if not d["courses"]:
            self.empty_state(lst, "No courses found for you.")
            return
        slots = defaultdict(list)
        for t in d["timetable"]:
            slots[t["code"]].append(t)
        for c in d["courses"]:
            item = ctk.CTkFrame(lst, fg_color=CARD, corner_radius=14)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(item, text=c["code"], font=font(18, True), fg_color=BRAND, text_color="#FFFFFF",
                         corner_radius=12, width=96, height=64).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(mid, text=c["course"], font=font(16, True), text_color=TEXT).pack(anchor="w")
            ctk.CTkLabel(mid, text=("Teacher: " + c["teacher"]) if c["teacher"]
                         else "Teacher not assigned yet", font=font(13),
                         text_color=MUTED).pack(anchor="w")
            rows = slots.get(c["code"], [])
            when = "   |   ".join(f"{academic.WEEKDAY_NAMES[r['day']]} {r['start']}-{r['end']} "
                                  f"(Room {r['room']})" for r in rows)
            ctk.CTkLabel(mid, text=when or "Class time not published yet", font=font(12, True),
                         text_color=CHIP_TEXT, wraplength=620, justify="left").pack(anchor="w", pady=(4, 0))
            chip(item, f"{len(rows)} class/week").grid(row=0, column=2, padx=18)

    def marks_tab(self, tab, d):
        lst = self.scroll(tab)
        if not d["sem"]:
            self.empty_state(lst, "No active semester yet.")
            return
        mx = float(d["settings"]["max_marks"])
        got = [(c, d["marks"].get(c["course_id"])) for c in d["courses"]]
        done = [m for _, m in got if m is not None]
        row = ctk.CTkFrame(lst, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        text = (f"Published: {len(done)} of {len(got)} courses"
                + (f"   |   Average: {sum(done) / len(done):.1f} / {mx:g}" if done else ""))
        ctk.CTkLabel(row, text=text, font=font(14, True), text_color=CHIP_TEXT).pack(anchor="w")
        for c, m in got:
            item = ctk.CTkFrame(lst, fg_color=CARD, corner_radius=14)
            item.pack(fill="x", pady=5)
            item.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(item, text=c["code"], font=font(16, True), text_color=TEXT, width=90).grid(
                row=0, column=0, padx=(18, 10), pady=16)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(mid, text=c["course"], font=font(14, True), text_color=TEXT).pack(anchor="w")
            ctk.CTkLabel(mid, text=("Teacher: " + c["teacher"]) if c["teacher"] else "Teacher not assigned",
                         font=font(12), text_color=MUTED).pack(anchor="w")
            right = ctk.CTkFrame(item, fg_color="transparent")
            right.grid(row=0, column=2, padx=18)
            if m is None:
                chip(right, "Not published yet", CARD_SOFT, MUTED).pack()
            else:
                letter = academic.grade_for(m, mx)
                ctk.CTkLabel(right, text=f"{m:g} / {mx:g}", font=font(20, True),
                             text_color=TEXT).pack(side="left", padx=(0, 12))
                chip(right, letter, GOOD if letter != "F" else BAD,
                     "#052E16" if letter != "F" else "#FFFFFF").pack(side="left")
