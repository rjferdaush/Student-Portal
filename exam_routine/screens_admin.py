"""Admin panel: routines, semesters, teacher courses, time settings, class routine."""
import contextlib
import gc
import queue
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import academic
import queries
from db import get_connection
from ui_kit import (ACCENT, ACCENT_HOVER, BAD, BG, CARD, CARD_SOFT, CHIP_TEXT, DONE, GOOD, MUTED,
                    TEXT, Dashboard, QueueWriter, TimetableGrid, chip, font, stat_card)


def entry(parent, text="", placeholder="", width=None, **kw):
    e = ctk.CTkEntry(parent, height=38, fg_color=CARD, border_color=CARD_SOFT, text_color=TEXT,
                     placeholder_text=placeholder, **({"width": width} if width else {}), **kw)
    if text:
        e.insert(0, text)
    return e


def label(parent, text, size=12, bold=False, color=MUTED, **kw):
    return ctk.CTkLabel(parent, text=text, font=font(size, bold), text_color=color, **kw)


def combo(parent, values, width=260, command=None):
    return ctk.CTkComboBox(parent, values=values or [""], width=width, height=38, command=command,
                           fg_color=CARD, border_color=CARD_SOFT, button_color=ACCENT,
                           button_hover_color=ACCENT_HOVER, dropdown_fg_color=CARD,
                           text_color=TEXT, dropdown_text_color=TEXT)


class AdminFrame(Dashboard):
    def __init__(self, app):
        super().__init__(app, "Admin", "Administrator")
        self.q = queue.Queue()
        self.busy = False
        self.log_target = None
        self.task_buttons = []
        self.stat_boxes = {}
        self.header("Admin panel", "Semesters, teachers, time settings, routines and more.")
        self.build_stats()
        _, tabs = self.make_tabs(["Routine tools", "Semesters", "Assign courses", "Time settings",
                                  "Class routine", "Teacher IDs"])
        self.build_tools(tabs["Routine tools"])
        self.build_semesters(tabs["Semesters"])
        self.build_assign(tabs["Assign courses"])
        self.build_settings(tabs["Time settings"])
        self.build_class_routine(tabs["Class routine"])
        self.build_teachers(tabs["Teacher IDs"])
        self.refresh_all()
        self.after(100, self.poll)

    # ------------------------------------------------------------ top stats
    def build_stats(self):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(14, 10))
        spec = (("students", "Students"), ("courses", "Courses"), ("teachers", "Teachers"),
                ("rooms", "Rooms"), ("exams", "Exams"), ("duties", "Duties"))
        colors = (ACCENT, GOOD, "#F59E0B", "#38BDF8", "#EC4899", "#A78BFA")
        for i, ((key, title), color) in enumerate(zip(spec, colors)):
            row.grid_columnconfigure(i, weight=1, uniform="adm")
            box = stat_card(row, title, "0", color)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            self.stat_boxes[key] = box

    def refresh_all(self):
        try:
            conn = get_connection()
        except Exception:
            return
        try:
            data = queries.counts(conn)
        finally:
            conn.close()
        for key, box in self.stat_boxes.items():
            box.value_label.configure(text=str(data.get(key, 0)))
        self.fill_teachers()
        self.refresh_semesters()
        self.reload_lookup()
        self.refresh_assignments()
        self.reload_preview_boxes()

    # ----------------------------------------------------- background tasks
    def make_log(self, parent, text):
        box = ctk.CTkTextbox(parent, fg_color=BG, text_color="#C7D2FE", corner_radius=12,
                             font=ctk.CTkFont(family="Courier", size=12), wrap="none")
        box.insert("end", text + "\n")
        box.configure(state="disabled")
        return box

    def log(self, text, box=None):
        box = box or self.log_target
        if box is None:
            return
        box.configure(state="normal")
        box.insert("end", text)
        box.see("end")
        box.configure(state="disabled")

    def poll(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                item = self.q.get_nowait()
                if item is DONE:
                    gc.enable()                    # was paused while the background task ran
                    self.busy = False
                    for b in self.task_buttons:
                        b.configure(state="normal")
                    self.refresh_all()
                else:
                    self.log(item)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def run_task(self, title, fn, log_box):
        if self.busy:
            return
        self.busy = True
        self.log_target = log_box
        for b in self.task_buttons:
            b.configure(state="disabled")
        self.log(f"\n>>> {title}\n")
        gc.disable()   # Tk objects must not be cleaned up from the worker thread (it can freeze)

        def work():
            try:
                with contextlib.redirect_stdout(QueueWriter(self.q)):
                    fn()
            except Exception as e:
                traceback.print_exc()
                self.q.put(f"\nERROR: {e}\n")
            self.q.put(DONE)

        threading.Thread(target=work, daemon=True).start()

    # ======================================================== Routine tools
    def build_tools(self, tab):
        tab.grid_columnconfigure(0, weight=2, uniform="t")
        tab.grid_columnconfigure(1, weight=3, uniform="t")
        tab.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 12), pady=8)
        label(left, "Step 1: Import CSV data", 15, True, TEXT).pack(anchor="w")
        label(left, "Folder with students, enrollments, courses,\nteachers and rooms CSV files.",
              justify="left").pack(anchor="w", pady=(0, 6))
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x")
        self.folder_entry = entry(row, str(Path(__file__).parent / "data"))
        self.folder_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Browse", width=76, height=38, fg_color=CARD, hover_color=CARD_SOFT,
                      text_color=TEXT, command=self.browse).pack(side="left", padx=(8, 0))
        self.clear_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left, text="Delete old data first (recommended)", variable=self.clear_var,
                        font=font(12), text_color=MUTED, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                        checkbox_width=18, checkbox_height=18).pack(anchor="w", pady=(10, 0))
        self.import_btn = ctk.CTkButton(left, text="Import data", height=42, corner_radius=10,
                                        fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                        font=font(14, True), command=self.on_import)
        self.import_btn.pack(fill="x", pady=(10, 22))

        label(left, "Step 2: Generate exam routine", 15, True, TEXT).pack(anchor="w")
        label(left, "First possible exam date (YYYY-MM-DD).\nExam time and exam days come from "
                    "Time settings.", justify="left").pack(anchor="w", pady=(0, 6))
        self.date_entry = entry(left, "2026-11-08")
        self.date_entry.pack(fill="x")
        self.gen_btn = ctk.CTkButton(left, text="Generate exam routine", height=42, corner_radius=10,
                                     fg_color=GOOD, hover_color="#16A34A", text_color="#052E16",
                                     font=font(14, True), command=self.on_generate)
        self.gen_btn.pack(fill="x", pady=(10, 0))
        self.task_buttons += [self.import_btn, self.gen_btn]

        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
        head = ctk.CTkFrame(right, fg_color="transparent")
        head.pack(fill="x")
        label(head, "Activity log", 15, True, TEXT).pack(side="left")
        self.tools_log = self.make_log(right, "Ready. Step 1: import data, then Step 2: generate the "
                                              "exam routine.")
        ctk.CTkButton(head, text="Clear", width=64, height=28, fg_color=CARD, hover_color=CARD_SOFT,
                      text_color=TEXT, command=lambda: self.clear_log(self.tools_log)).pack(side="right")
        self.tools_log.pack(fill="both", expand=True, pady=(6, 0))

    def clear_log(self, box):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.configure(state="disabled")

    def browse(self):
        folder = filedialog.askdirectory(title="Choose the folder with the CSV files")
        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def on_import(self):
        folder = self.folder_entry.get().strip()
        clear = self.clear_var.get()

        def task():
            import import_csv
            import run_all
            import_csv.DATA = Path(folder)
            data, errors = import_csv.validate()
            if errors:
                print(f"{len(errors)} error(s) found. Nothing was saved:")
                for e in errors:
                    print(" -", e)
                return
            print("CSV files are OK. Saving to MySQL...")
            conn = get_connection(with_database=False)
            try:
                run_all.run_schema(conn)
                if clear:
                    import_csv.clear_all(conn)
                    print("Old data removed.")
                import_csv.save(conn, data)
            finally:
                conn.close()
            print("Import finished.")

        self.run_task("Import CSV data", task, self.tools_log)

    def on_generate(self):
        try:
            start = datetime.strptime(self.date_entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            self.log("\nERROR: date must look like 2026-11-08\n", self.tools_log)
            return

        def task():
            import allocate_rooms
            import assign_teachers
            import scheduler
            conn = get_connection()
            try:
                st = academic.get_settings(conn)
                academic.apply_exam_slots(conn, st)
            finally:
                conn.close()
            scheduler.START_DATE = start
            scheduler.EXAM_WEEKDAYS = set(academic.parse_days(st["exam_days"]))
            print("Step 1 of 3: scheduling exams")
            scheduler.main()
            print("\nStep 2 of 3: allocating rooms and seats")
            allocate_rooms.main()
            print("\nStep 3 of 3: assigning teachers")
            assign_teachers.main()
            print("\nAll done. Students and teachers can now see the exam routine.")

        self.run_task("Generate exam routine", task, self.tools_log)

    # ============================================================= Semesters
    def build_semesters(self, tab):
        tab.grid_columnconfigure(0, weight=2, uniform="s")
        tab.grid_columnconfigure(1, weight=3, uniform="s")
        tab.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 12), pady=8)
        label(left, "New semester", 15, True, TEXT).pack(anchor="w")
        label(left, "Name and duration (date, month, year).").pack(anchor="w", pady=(0, 8))
        label(left, "SEMESTER NAME", 11, True).pack(anchor="w")
        self.sem_name = entry(left, placeholder="Spring 2026")
        self.sem_name.pack(fill="x", pady=(2, 8))
        label(left, "START DATE (YYYY-MM-DD)", 11, True).pack(anchor="w")
        self.sem_start = entry(left, placeholder="2026-01-01")
        self.sem_start.pack(fill="x", pady=(2, 8))
        label(left, "END DATE (YYYY-MM-DD)", 11, True).pack(anchor="w")
        self.sem_end = entry(left, placeholder="2026-06-30")
        self.sem_end.pack(fill="x", pady=(2, 10))
        ctk.CTkButton(left, text="Create semester", height=42, corner_radius=10, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, font=font(14, True), command=self.on_create_semester).pack(
            fill="x")
        self.sem_msg = label(left, "", 13, wraplength=300, justify="left")
        self.sem_msg.pack(anchor="w", pady=8)
        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
        label(right, "Semesters", 15, True, TEXT).pack(anchor="w", pady=(0, 6))
        self.sem_list = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.sem_list.pack(fill="both", expand=True)

    def on_create_semester(self):
        conn = get_connection()
        try:
            ok, msg = academic.create_semester(conn, self.sem_name.get(), self.sem_start.get(),
                                               self.sem_end.get())
        finally:
            conn.close()
        self.sem_msg.configure(text=msg, text_color=GOOD if ok else BAD)
        if ok:
            for e in (self.sem_name, self.sem_start, self.sem_end):
                e.delete(0, "end")
            self.refresh_semesters()
            self.refresh_assignments()

    def refresh_semesters(self):
        for w in self.sem_list.winfo_children():
            w.destroy()
        conn = get_connection()
        try:
            sems = academic.list_semesters(conn)
        finally:
            conn.close()
        if not sems:
            label(self.sem_list, "No semester yet. Create the first one on the left.", 14).pack(
                pady=30)
        for s in sems:
            row = ctk.CTkFrame(self.sem_list, fg_color=CARD, corner_radius=12)
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(0, weight=1)
            mid = ctk.CTkFrame(row, fg_color="transparent")
            mid.grid(row=0, column=0, sticky="w", padx=16, pady=12)
            label(mid, s["name"], 16, True, TEXT).pack(anchor="w")
            label(mid, f"{s['start'].strftime('%d %b %Y')}  to  {s['end'].strftime('%d %b %Y')}",
                  12).pack(anchor="w")
            right = ctk.CTkFrame(row, fg_color="transparent")
            right.grid(row=0, column=1, padx=12)
            if s["active"]:
                chip(right, "ACTIVE", GOOD, "#052E16").pack(side="left", padx=4)
            else:
                ctk.CTkButton(right, text="Set active", width=90, height=30, fg_color=ACCENT,
                              hover_color=ACCENT_HOVER,
                              command=lambda i=s["id"]: self.set_active(i)).pack(side="left", padx=4)
            ctk.CTkButton(right, text="Delete", width=70, height=30, fg_color=CARD_SOFT,
                          hover_color="#7F1D1D", text_color=TEXT,
                          command=lambda i=s["id"], n=s["name"]: self.delete_semester(i, n)).pack(
                side="left", padx=4)

    def set_active(self, sid):
        conn = get_connection()
        try:
            academic.set_active_semester(conn, sid)
        finally:
            conn.close()
        self.refresh_semesters()
        self.refresh_assignments()

    def delete_semester(self, sid, name):
        if not messagebox.askyesno("Delete semester",
                                   f"Delete '{name}' with its teacher courses, class routine and "
                                   f"marks?\nThis cannot be undone."):
            return
        conn = get_connection()
        try:
            academic.delete_semester(conn, sid)
        finally:
            conn.close()
        self.refresh_semesters()
        self.refresh_assignments()

    # ======================================================= Assign courses
    def build_assign(self, tab):
        self.assign_info = label(tab, "", 13, True, CHIP_TEXT)
        self.assign_info.pack(anchor="w", padx=12, pady=(10, 4))
        form = ctk.CTkFrame(tab, fg_color="transparent")
        form.pack(fill="x", padx=8)
        self.teacher_combo = combo(form, [], 270)
        self.teacher_combo.pack(side="left", padx=4)
        self.course_combo = combo(form, [], 270, command=lambda v: self.on_course_pick())
        self.course_combo.pack(side="left", padx=4)
        self.section_combo = combo(form, [], 200)
        self.section_combo.pack(side="left", padx=4)
        ctk.CTkButton(form, text="Assign", width=90, height=38, fg_color=GOOD, hover_color="#16A34A",
                      text_color="#052E16", font=font(13, True), command=self.on_assign).pack(
            side="left", padx=4)
        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=8)
        ctk.CTkButton(row2, text="Auto-assign all unassigned", height=36, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, text_color="#FFFFFF", command=self.on_auto_assign).pack(side="left", padx=4)
        ctk.CTkButton(row2, text="Clear all", height=36, width=90, fg_color=CARD_SOFT,
                      hover_color="#7F1D1D", text_color=TEXT, command=self.on_clear_assign).pack(
            side="left", padx=4)
        self.assign_search = entry(row2, placeholder="Search teacher, course or section", width=260)
        self.assign_search.pack(side="right", padx=4)
        self.assign_search.bind("<KeyRelease>", lambda e: self.refresh_assignments())
        self.assign_msg = label(tab, "", 13, wraplength=900, justify="left")
        self.assign_msg.pack(anchor="w", padx=12)
        self.assign_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.assign_list.pack(fill="both", expand=True, padx=4, pady=(4, 6))
        self.teacher_map, self.course_map = {}, {}

    def reload_lookup(self):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT teacher_id, name, rank_type FROM teachers ORDER BY teacher_id")
            teachers = cur.fetchall()
            cur.execute("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cur.fetchall()
        finally:
            conn.close()
        self.teacher_map = {f"{t[0]} - {t[1]} ({t[2]})": t[0] for t in teachers}
        self.course_map = {f"{c[1]} - {c[2]}": c[0] for c in courses}
        self.teacher_combo.configure(values=list(self.teacher_map) or [""])
        self.course_combo.configure(values=list(self.course_map) or [""])
        self.teacher_combo.set(next(iter(self.teacher_map), "Choose teacher"))
        self.course_combo.set(next(iter(self.course_map), "Choose course"))
        self.on_course_pick()

    def on_course_pick(self):
        cid = self.course_map.get(self.course_combo.get())
        self.section_map = {}
        if cid:
            conn = get_connection()
            try:
                rows = academic.sections_for_course(conn, cid)
            finally:
                conn.close()
            self.section_map = {f"Section {sec} ({n} students)": sec for sec, n in rows}
        self.section_combo.configure(values=list(self.section_map) or [""])
        self.section_combo.set(next(iter(self.section_map), "Section"))

    def active_sem(self):
        conn = get_connection()
        try:
            return academic.active_semester(conn)
        finally:
            conn.close()

    def on_assign(self):
        sem = self.active_sem()
        tid = self.teacher_map.get(self.teacher_combo.get())
        cid = self.course_map.get(self.course_combo.get())
        sec = getattr(self, "section_map", {}).get(self.section_combo.get())
        if not sem:
            self.assign_msg.configure(text="Create and activate a semester first.", text_color=BAD)
            return
        if not (tid and cid and sec):
            self.assign_msg.configure(text="Choose a teacher, a course and a section.", text_color=BAD)
            return
        conn = get_connection()
        try:
            academic.add_assignment(conn, sem["id"], tid, cid, sec)
        finally:
            conn.close()
        self.assign_msg.configure(text="Assigned. Generate the class routine again to update times.",
                                  text_color=GOOD)
        self.refresh_assignments()

    def on_auto_assign(self):
        sem = self.active_sem()
        if not sem:
            self.assign_msg.configure(text="Create and activate a semester first.", text_color=BAD)
            return
        conn = get_connection()
        try:
            n = academic.auto_assign(conn, sem["id"])
        finally:
            conn.close()
        self.assign_msg.configure(
            text=f"Assigned {n} course section(s) fairly among teachers. You can change any of them.",
            text_color=GOOD)
        self.refresh_assignments()

    def on_clear_assign(self):
        sem = self.active_sem()
        if not sem or not messagebox.askyesno("Clear", "Remove ALL teacher course assignments of "
                                                       "this semester?"):
            return
        conn = get_connection()
        try:
            academic.clear_assignments(conn, sem["id"])
        finally:
            conn.close()
        self.assign_msg.configure(text="All assignments removed.", text_color=GOOD)
        self.refresh_assignments()

    def refresh_assignments(self):
        for w in self.assign_list.winfo_children():
            w.destroy()
        conn = get_connection()
        try:
            sem = academic.active_semester(conn)
            rows = academic.list_assignments(conn, sem["id"], self.assign_search.get()) if sem else []
        finally:
            conn.close()
        self.assign_info.configure(
            text=("Active semester: " + academic.semester_text(sem)) if sem
            else "No active semester. Create one in the Semesters tab.")
        if not rows:
            label(self.assign_list, "No assignments to show.", 14).pack(pady=24)
            return
        shown = rows[:60]
        for r in shown:
            line = ctk.CTkFrame(self.assign_list, fg_color=CARD, corner_radius=10)
            line.pack(fill="x", pady=3, padx=2)
            label(line, f"{r['teacher']}  (ID {r['teacher_id']})", 13, True, TEXT, width=250,
                  anchor="w").pack(side="left", padx=(14, 6), pady=8)
            label(line, f"{r['code']} - {r['course']}", 13, False, CHIP_TEXT, width=300,
                  anchor="w").pack(side="left")
            label(line, f"Sec {r['section']}", 12, True, MUTED, width=70).pack(side="left")
            label(line, f"{r['size']} students", 12, False, MUTED, width=90).pack(side="left")
            ctk.CTkButton(line, text="Remove", width=72, height=28, fg_color=CARD_SOFT,
                          hover_color="#7F1D1D", text_color=TEXT,
                          command=lambda i=r["id"]: self.remove_assignment(i)).pack(side="right", padx=10)
        if len(rows) > len(shown):
            label(self.assign_list, f"Showing the first {len(shown)} of {len(rows)}. "
                                    f"Use the search box to find others.", 12).pack(pady=8)

    def remove_assignment(self, aid):
        conn = get_connection()
        try:
            academic.remove_assignment(conn, aid)
        finally:
            conn.close()
        self.refresh_assignments()

    # ========================================================= Time settings
    def build_settings(self, tab):
        box = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        box.pack(fill="both", expand=True)
        box.grid_columnconfigure(0, weight=1, uniform="c")
        box.grid_columnconfigure(1, weight=1, uniform="c")
        self.set_entries, self.day_vars = {}, {}
        s = self.current_settings()

        def card(col, title, subtitle):
            c = ctk.CTkFrame(box, fg_color=CARD, corner_radius=14)
            c.grid(row=0, column=col, sticky="nsew", padx=8, pady=6)
            label(c, title, 16, True, TEXT).pack(anchor="w", padx=18, pady=(16, 0))
            label(c, subtitle).pack(anchor="w", padx=18, pady=(0, 8))
            return c

        def field(c, key, text, hint):
            label(c, text, 11, True).pack(anchor="w", padx=18)
            e = entry(c, s[key], hint)
            e.pack(fill="x", padx=18, pady=(2, 8))
            self.set_entries[key] = e

        def days(c, kind, title):
            label(c, title, 11, True).pack(anchor="w", padx=18, pady=(4, 2))
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(0, 14))
            chosen = academic.parse_days(s[kind + "_days"])
            for d in academic.WEEK_ORDER:
                var = ctk.BooleanVar(value=d in chosen)
                self.day_vars[(kind, d)] = var
                ctk.CTkCheckBox(row, text=academic.WEEKDAY_NAMES[d], variable=var, width=60,
                                font=font(12), text_color=TEXT, fg_color=ACCENT,
                                hover_color=ACCENT_HOVER, checkbox_width=16,
                                checkbox_height=16).pack(side="left", padx=4)

        ex = card(0, "Exam time", "Set by the admin. The exam routine follows this.")
        field(ex, "exam_start", "FIRST EXAM STARTS AT (HH:MM)", "09:00")
        field(ex, "exam_duration", "EXAM DURATION (MINUTES)", "120")
        field(ex, "exam_gap", "GAP BETWEEN EXAMS (MINUTES)", "30")
        field(ex, "exam_slots", "EXAM TIME SLOTS PER DAY", "4")
        days(ex, "exam", "EXAM DAYS")

        cl = card(1, "Class time", "Set by the admin. The class routine follows this.")
        field(cl, "class_start", "FIRST CLASS STARTS AT (HH:MM)", "08:30")
        field(cl, "class_duration", "CLASS DURATION (MINUTES)", "45")
        field(cl, "class_gap", "BREAK BETWEEN CLASSES (MINUTES)", "5")
        field(cl, "class_periods", "CLASS PERIODS PER DAY", "6")
        field(cl, "classes_per_week", "CLASSES PER WEEK FOR EACH COURSE", "2")
        field(cl, "max_marks", "TOTAL MARKS FOR EXAM MARKS ENTRY", "100")
        days(cl, "class", "CLASS DAYS")

        bottom = ctk.CTkFrame(box, fg_color="transparent")
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        ctk.CTkButton(bottom, text="Save settings", height=42, width=200, corner_radius=10,
                      fg_color=GOOD, hover_color="#16A34A", text_color="#052E16", font=font(14, True),
                      command=self.on_save_settings).pack(anchor="w")
        self.settings_msg = label(bottom, "", 13, wraplength=900, justify="left")
        self.settings_msg.pack(anchor="w", pady=(8, 0))
        self.settings_preview = label(bottom, "", 12, False, CHIP_TEXT, wraplength=900, justify="left")
        self.settings_preview.pack(anchor="w", pady=(4, 0))
        self.show_preview(s)

    def current_settings(self):
        conn = get_connection()
        try:
            return academic.get_settings(conn)
        finally:
            conn.close()

    def show_preview(self, s):
        try:
            ex = " | ".join(f"{a}-{b}" for _, a, b in academic.make_periods(
                s["exam_start"], s["exam_duration"], s["exam_gap"], s["exam_slots"]))
            cl = " | ".join(f"{a}-{b}" for _, a, b in academic.class_periods(s))
            self.settings_preview.configure(text=f"Exam slots: {ex}\nClass periods: {cl}")
        except ValueError:
            pass

    def on_save_settings(self):
        vals = {k: e.get().strip() for k, e in self.set_entries.items()}
        for kind in ("exam", "class"):
            chosen = [d for d in academic.WEEK_ORDER if self.day_vars[(kind, d)].get()]
            vals[kind + "_days"] = ",".join(str(d) for d in chosen)
        try:
            for key in ("exam_duration", "exam_slots", "class_duration", "class_periods",
                        "classes_per_week"):
                if int(vals[key]) <= 0:
                    raise ValueError(f"{key.replace('_', ' ')} must be a positive number")
            for key in ("exam_gap", "class_gap"):
                if int(vals[key]) < 0:
                    raise ValueError("gap cannot be negative")
            if float(vals["max_marks"]) <= 0:
                raise ValueError("total marks must be positive")
            academic.make_periods(vals["exam_start"], vals["exam_duration"], vals["exam_gap"],
                                  vals["exam_slots"])
            academic.make_periods(vals["class_start"], vals["class_duration"], vals["class_gap"],
                                  vals["class_periods"])
            if not vals["exam_days"] or not vals["class_days"]:
                raise ValueError("choose at least one exam day and one class day")
        except ValueError as e:
            self.settings_msg.configure(text=f"Please check: {e}", text_color=BAD)
            return
        conn = get_connection()
        try:
            academic.set_settings(conn, vals)
            _, cleared = academic.apply_exam_slots(conn, academic.get_settings(conn))
        finally:
            conn.close()
        msg = "Settings saved. Generate the exam routine and the class routine again to use them."
        if cleared:
            msg += " (The old exam routine was removed because exam slots were reduced.)"
        self.settings_msg.configure(text=msg, text_color=GOOD)
        self.show_preview(vals)

    # ======================================================== Class routine
    def build_class_routine(self, tab):
        tab.grid_columnconfigure(0, weight=2, uniform="r")
        tab.grid_columnconfigure(1, weight=5, uniform="r")
        tab.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 10), pady=8)
        label(left, "Generate class routine", 15, True, TEXT).pack(anchor="w")
        label(left, "Uses the active semester, teacher courses,\nclass time and rooms. No teacher, "
                    "student or\nroom clash.", justify="left").pack(anchor="w", pady=(0, 8))
        self.class_btn = ctk.CTkButton(left, text="Generate class routine", height=42, corner_radius=10,
                                       fg_color=GOOD, hover_color="#16A34A", text_color="#052E16",
                                       font=font(14, True), command=self.on_class_routine)
        self.class_btn.pack(fill="x")
        self.task_buttons.append(self.class_btn)
        self.class_log = self.make_log(left, "Ready.")
        self.class_log.pack(fill="both", expand=True, pady=(10, 0))

        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
        label(right, "Preview a section", 15, True, TEXT).pack(anchor="w")
        row = ctk.CTkFrame(right, fg_color="transparent")
        row.pack(fill="x", pady=(6, 8))
        self.pv_class = combo(row, [], 150, command=lambda v: self.on_pv_class())
        self.pv_class.pack(side="left")
        self.pv_section = combo(row, [], 110)
        self.pv_section.pack(side="left", padx=8)
        ctk.CTkButton(row, text="Show", width=80, height=38, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.show_preview_grid).pack(side="left")
        self.pv_msg = label(row, "", 12)
        self.pv_msg.pack(side="left", padx=12)
        self.pv_area = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.pv_area.pack(fill="both", expand=True)
        self.pv_data = {}

    def on_class_routine(self):
        import class_scheduler

        def task():
            conn = get_connection()
            try:
                sem = academic.active_semester(conn)
                if not sem:
                    print("No active semester. Create one in the Semesters tab.")
                    return
                print("Semester:", academic.semester_text(sem))
                print(class_scheduler.generate(conn, sem["id"])[2])
            finally:
                conn.close()

        self.run_task("Generate class routine", task, self.class_log)

    def reload_preview_boxes(self):
        conn = get_connection()
        try:
            self.pv_data = academic.class_and_sections(conn)
        finally:
            conn.close()
        names = list(self.pv_data)
        self.pv_class.configure(values=names or [""])
        self.pv_class.set(names[0] if names else "Class")
        self.on_pv_class()

    def on_pv_class(self):
        secs = self.pv_data.get(self.pv_class.get(), [])
        self.pv_section.configure(values=secs or [""])
        self.pv_section.set(secs[0] if secs else "Section")

    def show_preview_grid(self):
        for w in self.pv_area.winfo_children():
            w.destroy()
        conn = get_connection()
        try:
            sem = academic.active_semester(conn)
            if not sem:
                self.pv_msg.configure(text="No active semester.", text_color=BAD)
                return
            items = academic.section_timetable(conn, self.pv_class.get(), self.pv_section.get(), sem["id"])
            st = academic.get_settings(conn)
        finally:
            conn.close()
        if not items:
            self.pv_msg.configure(text="No class routine for this section yet.", text_color=BAD)
            return
        self.pv_msg.configure(text=f"{len(items)} classes per week", text_color=GOOD)
        TimetableGrid(self.pv_area, academic.class_periods(st), academic.parse_days(st["class_days"]),
                      items, lambda it: [it["code"], it["teacher"], f"Room {it['room']}"]).pack(
            fill="x", padx=4)

    # ============================================================ Teacher IDs
    def build_teachers(self, tab):
        label(tab, "Give each teacher their ID. Teachers use it to register and login.", 13).pack(
            anchor="w", padx=12, pady=(10, 6))
        self.teacher_box = ctk.CTkTextbox(tab, fg_color=BG, text_color="#C7D2FE", corner_radius=12,
                                          font=ctk.CTkFont(family="Courier", size=13))
        self.teacher_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def fill_teachers(self):
        conn = get_connection()
        try:
            rows = queries.teacher_list(conn)
        finally:
            conn.close()
        self.teacher_box.configure(state="normal")
        self.teacher_box.delete("1.0", "end")
        self.teacher_box.insert("end", f"{'ID':<6}{'Name':<24}Rank\n{'-' * 42}\n")
        for tid, name, rank in rows:
            self.teacher_box.insert("end", f"{tid:<6}{name:<24}{rank}\n")
        if not rows:
            self.teacher_box.insert("end", "No teachers yet. Import the CSV data first.\n")
        self.teacher_box.configure(state="disabled")
