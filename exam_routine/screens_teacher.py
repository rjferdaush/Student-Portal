"""Teacher dashboard: courses, class routine, marks entry, exam routine and duties."""
from datetime import date

import customtkinter as ctk

import academic
import queries
from db import get_connection
from ui_kit import (ACCENT, BAD, BRAND, CARD, CARD_SOFT, CHIP_TEXT, GOOD, MUTED, TEXT, Dashboard,
                    TimetableGrid, chip, date_block, font, status_for)


class TeacherFrame(Dashboard):
    def __init__(self, app, teacher_id, name):
        super().__init__(app, "Teacher", name)
        self.teacher_id = int(teacher_id)
        self.name = name
        self.render()

    def load(self):
        conn = get_connection()
        try:
            d = dict(info=queries.teacher_info(conn, self.teacher_id),
                     duties=queries.teacher_duties(conn, self.teacher_id),
                     sem=academic.active_semester(conn),
                     settings=academic.get_settings(conn))
            sid = d["sem"]["id"] if d["sem"] else 0
            d["assign"] = academic.teacher_assignments(conn, self.teacher_id, sid) if sid else []
            d["timetable"] = academic.teacher_timetable(conn, self.teacher_id, sid) if sid else []
            d["exam_rooms"] = {a["id"]: academic.assignment_exam_rooms(conn, a["course_id"], a["section"])
                               for a in d["assign"]}
        finally:
            conn.close()
        return d

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        d = self.load()
        info, sem = d["info"], d["sem"]
        sub = f"Teacher ID {self.teacher_id}   |   {info['rank'].title()}   |   {info['dept']}"
        sub += ("\nSemester: " + academic.semester_text(sem)) if sem else "\nNo active semester yet"
        self.header(f"Hello, {self.name}", sub, self.render)
        self.d = d
        self.stats_row([
            ("My courses", len(d["assign"]), ACCENT),
            ("Students", sum(a["size"] for a in d["assign"]), GOOD),
            ("Classes per week", len(d["timetable"]), "#38BDF8"),
            ("Exam duties", len(d["duties"]), "#F59E0B"),
        ])
        _, tabs = self.make_tabs(["My courses", "Class routine", "Marks", "Exam routine", "Exam duty"])
        self.courses_tab(tabs["My courses"])
        self.class_tab(tabs["Class routine"])
        self.marks_tab(tabs["Marks"])
        self.exam_tab(tabs["Exam routine"])
        self.duty_tab(tabs["Exam duty"])

    # ---------------------------------------------------------------- tabs
    def courses_tab(self, tab):
        lst = self.scroll(tab)
        d = self.d
        if not d["assign"]:
            self.empty_state(lst, "No course is assigned to you in this semester yet.\n"
                                  "The admin assigns courses to teachers.")
            return
        for a in d["assign"]:
            rows = [t for t in d["timetable"] if t["assignment"] == a["id"]]
            item = ctk.CTkFrame(lst, fg_color=CARD, corner_radius=14)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(item, text=a["code"], font=font(18, True), fg_color=BRAND, text_color="#FFFFFF",
                         corner_radius=12, width=96, height=64).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(mid, text=a["course"], font=font(16, True), text_color=TEXT).pack(anchor="w")
            ctk.CTkLabel(mid, text=f"Class: {a['klass'] or '-'}   |   Section {a['section']}   |   "
                                   f"{a['size']} students", font=font(13), text_color=MUTED).pack(anchor="w")
            when = "   |   ".join(f"{academic.WEEKDAY_NAMES[r['day']]} {r['start']}-{r['end']} "
                                  f"(Room {r['room']})" for r in rows)
            ctk.CTkLabel(mid, text=when or "Class time not published yet", font=font(12, True),
                         text_color=CHIP_TEXT, wraplength=620, justify="left").pack(anchor="w", pady=(4, 0))
            chip(item, f"{len(rows)} class/week").grid(row=0, column=2, padx=18)

    def class_tab(self, tab):
        box = self.scroll(tab)
        d = self.d
        if not d["timetable"]:
            self.empty_state(box, "Your class routine is not published yet.")
            return
        s = d["settings"]
        TimetableGrid(box, academic.class_periods(s), academic.parse_days(s["class_days"]),
                      d["timetable"],
                      lambda it: [f"{it['code']}  Sec {it['section']}", f"Room {it['room']}"]).pack(
            fill="x", padx=4, pady=4)

    # ----- marks entry -----
    def marks_tab(self, tab):
        d = self.d
        if not d["assign"] or not d["sem"]:
            self.empty_state(self.scroll(tab), "No course is assigned to you yet, so there are no "
                                               "students to give marks.")
            return
        self.max_marks = float(d["settings"]["max_marks"])
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=6, pady=(6, 8))
        self.assign_map = {f"{a['code']} - {a['course']}  |  Section {a['section']}": a for a in d["assign"]}
        self.pick = ctk.CTkComboBox(top, values=list(self.assign_map), width=420, height=38,
                                    command=lambda v: self.load_roster(),
                                    fg_color=CARD, border_color=CARD_SOFT, button_color=ACCENT,
                                    dropdown_fg_color=CARD)
        self.pick.pack(side="left")
        ctk.CTkLabel(top, text=f"Marks out of {self.max_marks:g}", font=font(13, True),
                     text_color=CHIP_TEXT).pack(side="left", padx=14)
        self.save_btn = ctk.CTkButton(top, text="Save marks", width=120, height=38, fg_color=GOOD,
                                      hover_color="#16A34A", text_color="#052E16", font=font(13, True),
                                      command=self.save_marks)
        self.save_btn.pack(side="right")
        self.marks_msg = ctk.CTkLabel(tab, text="", font=font(13))
        self.marks_msg.pack(anchor="w", padx=8)
        self.roster_box = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.roster_box.pack(fill="both", expand=True)
        self.entries = []
        self.pick.set(list(self.assign_map)[0])
        self.load_roster()

    def current_assignment(self):
        return self.assign_map.get(self.pick.get())

    def load_roster(self):
        for w in self.roster_box.winfo_children():
            w.destroy()
        self.entries = []
        self.marks_msg.configure(text="")
        a = self.current_assignment()
        if not a:
            return
        conn = get_connection()
        try:
            roster = academic.marks_roster(conn, self.d["sem"]["id"], a["course_id"], a["section"])
        finally:
            conn.close()
        head = ctk.CTkFrame(self.roster_box, fg_color="transparent")
        head.pack(fill="x", padx=8)
        for text, w in (("Student ID", 110), ("Name", 260), ("Marks", 100), ("Grade", 60)):
            ctk.CTkLabel(head, text=text, width=w, anchor="w", font=font(12, True),
                         text_color=MUTED).pack(side="left", padx=(0, 8))
        for r in roster:
            row = ctk.CTkFrame(self.roster_box, fg_color=CARD, corner_radius=10)
            row.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(row, text=r["student_id"], width=110, anchor="w", font=font(13, True),
                         text_color=TEXT).pack(side="left", padx=(12, 8), pady=6)
            ctk.CTkLabel(row, text=r["name"], width=260, anchor="w", font=font(13),
                         text_color=MUTED).pack(side="left", padx=(0, 8))
            ent = ctk.CTkEntry(row, width=100, height=32, fg_color="#0F1530", border_color=CARD_SOFT,
                               placeholder_text="-", text_color=TEXT)
            if r["marks"] is not None:
                ent.insert(0, f"{r['marks']:g}")
            ent.pack(side="left", padx=(0, 8))
            grade = ctk.CTkLabel(row, text="", width=60, anchor="w", font=font(13, True), text_color=GOOD)
            grade.pack(side="left")
            ent.bind("<KeyRelease>", lambda e, en=ent, g=grade: self.preview_grade(en, g))
            self.preview_grade(ent, grade)
            self.entries.append((r["student_id"], ent))

    def preview_grade(self, entry, label):
        text = entry.get().strip()
        try:
            value = float(text)
            if text == "" or value < 0 or value > self.max_marks:
                raise ValueError
            letter = academic.grade_for(value, self.max_marks)
            label.configure(text=letter, text_color=GOOD if letter != "F" else BAD)
        except ValueError:
            label.configure(text="", text_color=GOOD)

    def save_marks(self):
        a = self.current_assignment()
        if not a:
            return
        conn = get_connection()
        try:
            ok, msg = academic.save_marks(conn, self.d["sem"]["id"], self.teacher_id, a["id"],
                                          [(sid, e.get()) for sid, e in self.entries], self.max_marks)
        finally:
            conn.close()
        self.marks_msg.configure(text=msg, text_color=GOOD if ok else BAD)

    # ----- exam routine of my sections -----
    def exam_tab(self, tab):
        lst = self.scroll(tab)
        d = self.d
        if not d["assign"]:
            self.empty_state(lst, "No course is assigned to you yet.")
            return
        for a in d["assign"]:
            card = ctk.CTkFrame(lst, fg_color=CARD, corner_radius=14)
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(card, text=f"{a['code']}  -  {a['course']}   (Section {a['section']})",
                         font=font(16, True), text_color=TEXT).pack(anchor="w", padx=18, pady=(14, 4))
            rows = d["exam_rooms"].get(a["id"], [])
            if not rows:
                ctk.CTkLabel(card, text="Exam routine is not published yet.", font=font(13),
                             text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 14))
            for r in rows:
                line = ctk.CTkFrame(card, fg_color="transparent")
                line.pack(fill="x", padx=18, pady=(0, 10))
                ctk.CTkLabel(line, text=r["date"].strftime("%a, %d %b %Y"), font=font(14, True),
                             text_color=CHIP_TEXT, width=150, anchor="w").pack(side="left")
                ctk.CTkLabel(line, text=f"{r['start']} - {r['end']}", font=font(14),
                             text_color=TEXT, width=120, anchor="w").pack(side="left")
                chip(line, f"Room {r['room']}", ACCENT, "#FFFFFF").pack(side="left", padx=6)
                chip(line, f"Seats {r['first']}-{r['last']}  ({r['students']} students)").pack(
                    side="left", padx=6)

    # ----- invigilation duty -----
    def duty_tab(self, tab):
        lst = self.scroll(tab)
        duties = self.d["duties"]
        if not duties:
            self.empty_state(lst, "No exam duty has been assigned to you yet.")
            return
        upcoming = [x["date"] for x in duties if x["date"] >= date.today()]
        next_date = min(upcoming) if upcoming else None
        for x in duties:
            status = status_for(x["date"], next_date)
            done = status == "DONE"
            item = ctk.CTkFrame(lst, fg_color=CARD, corner_radius=14)
            item.pack(fill="x", pady=6)
            item.grid_columnconfigure(1, weight=1)
            date_block(item, x["date"], done).grid(row=0, column=0, padx=14, pady=14)
            mid = ctk.CTkFrame(item, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="w")
            top = ctk.CTkFrame(mid, fg_color="transparent")
            top.pack(anchor="w")
            ctk.CTkLabel(top, text=x["code"], font=font(20, True),
                         text_color=MUTED if done else TEXT).pack(side="left")
            if status:
                chip(top, status, GOOD if status == "NEXT" else CARD_SOFT,
                     "#052E16" if status == "NEXT" else MUTED).pack(side="left", padx=10)
            ctk.CTkLabel(mid, text=x["course"], font=font(14), text_color=MUTED).pack(anchor="w")
            ctk.CTkLabel(mid, text=f"{x['start']} - {x['end']}     With: {x['partners']}",
                         font=font(13, True), text_color=CHIP_TEXT).pack(anchor="w", pady=(4, 0))
            right = ctk.CTkFrame(item, fg_color="transparent")
            right.grid(row=0, column=2, padx=18)
            chip(right, f"Room {x['building']}-{x['room']}", ACCENT, "#FFFFFF").pack(pady=3, anchor="e")
            chip(right, f"{x['students']} students").pack(pady=3, anchor="e")
