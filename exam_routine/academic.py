"""Semesters, teacher-course assignments, time settings and marks."""
from collections import defaultdict
from datetime import date, datetime

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]   # Python weekday numbers
WEEK_ORDER = [6, 0, 1, 2, 3, 4, 5]                                   # week starts on Sunday

ACADEMIC_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS settings (
         skey VARCHAR(50) PRIMARY KEY,
         svalue VARCHAR(200) NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS semesters (
         semester_id INT AUTO_INCREMENT PRIMARY KEY,
         name VARCHAR(60) UNIQUE NOT NULL,
         start_date DATE NOT NULL,
         end_date DATE NOT NULL,
         is_active TINYINT NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS teacher_courses (
         id INT AUTO_INCREMENT PRIMARY KEY,
         semester_id INT NOT NULL,
         teacher_id INT NOT NULL,
         course_id INT NOT NULL,
         section VARCHAR(5) NOT NULL,
         UNIQUE (semester_id, course_id, section),
         FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE,
         FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
         FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE)""",
    """CREATE TABLE IF NOT EXISTS class_routine (
         id INT AUTO_INCREMENT PRIMARY KEY,
         semester_id INT NOT NULL,
         assignment_id INT NOT NULL,
         weekday TINYINT NOT NULL,
         period_no TINYINT NOT NULL,
         start_time TIME NOT NULL,
         end_time TIME NOT NULL,
         room_id INT NOT NULL,
         UNIQUE (semester_id, room_id, weekday, period_no),
         FOREIGN KEY (assignment_id) REFERENCES teacher_courses(id) ON DELETE CASCADE,
         FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE)""",
    """CREATE TABLE IF NOT EXISTS marks (
         semester_id INT NOT NULL,
         student_id VARCHAR(20) NOT NULL,
         course_id INT NOT NULL,
         marks DECIMAL(6,2) NOT NULL,
         updated_by INT NULL,
         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
         PRIMARY KEY (semester_id, student_id, course_id),
         FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE,
         FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
         FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE)""",
]


def ensure_tables(conn):
    cur = conn.cursor()
    for stmt in ACADEMIC_SCHEMA:
        cur.execute(stmt)
    conn.commit()


# ---------------------------------------------------------------- settings
DEFAULTS = {
    "exam_start": "09:00", "exam_duration": "120", "exam_gap": "30", "exam_slots": "4",
    "exam_days": "6,1,3",
    "class_start": "08:30", "class_duration": "45", "class_gap": "5", "class_periods": "6",
    "class_days": "6,0,1,2,3", "classes_per_week": "2",
    "max_marks": "100",
}


def get_settings(conn):
    cur = conn.cursor()
    cur.execute("SELECT skey, svalue FROM settings")
    data = dict(DEFAULTS)
    data.update(dict(cur.fetchall()))
    return data


def set_settings(conn, values):
    cur = conn.cursor()
    for k, v in values.items():
        cur.execute("INSERT INTO settings (skey, svalue) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE svalue = %s", (k, str(v), str(v)))
    conn.commit()


def parse_days(text):
    days = [int(x) for x in str(text).split(",") if x.strip() != ""]
    return [d for d in WEEK_ORDER if d in days]


def parse_hhmm(text):
    h, m = str(text).strip().split(":")
    h, m = int(h), int(m)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("time must be HH:MM")
    return h * 60 + m


def fmt_hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def make_periods(start, duration, gap, count):
    """[(1, '09:00', '11:00'), ...] built from the admin's settings."""
    first = parse_hhmm(start)
    duration, gap, count = int(duration), int(gap), int(count)
    if duration <= 0 or gap < 0 or count <= 0:
        raise ValueError("duration, gap and number of periods must be positive")
    out = []
    for i in range(count):
        a = first + i * (duration + gap)
        b = a + duration
        if b >= 24 * 60:
            raise ValueError("these times go past midnight")
        out.append((i + 1, fmt_hhmm(a), fmt_hhmm(b)))
    return out


def class_periods(settings):
    return make_periods(settings["class_start"], settings["class_duration"],
                        settings["class_gap"], settings["class_periods"])


def apply_exam_slots(conn, settings):
    """Write the exam time slots (time_slots table) from the settings."""
    slots = make_periods(settings["exam_start"], settings["exam_duration"],
                         settings["exam_gap"], settings["exam_slots"])
    cur = conn.cursor()
    n = len(slots)
    cleared = False
    cur.execute("SELECT COUNT(*) FROM exams WHERE slot_id > %s", (n,))
    if cur.fetchone()[0]:
        for table in ("seat_plan", "invigilations", "exam_rooms", "exams"):
            try:
                cur.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        cleared = True
    for no, a, b in slots:
        cur.execute("INSERT INTO time_slots (slot_id, start_time, end_time) VALUES (%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE start_time=%s, end_time=%s", (no, a, b, a, b))
    cur.execute("DELETE FROM time_slots WHERE slot_id > %s", (n,))
    conn.commit()
    return slots, cleared


# --------------------------------------------------------------- semesters
def parse_date(text):
    return datetime.strptime(text.strip(), "%Y-%m-%d").date()


def create_semester(conn, name, start_text, end_text):
    name = name.strip()
    if not name:
        return False, "Please enter a semester name."
    try:
        start, end = parse_date(start_text), parse_date(end_text)
    except ValueError:
        return False, "Dates must look like 2026-01-01."
    if end <= start:
        return False, "End date must be after the start date."
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM semesters WHERE name=%s", (name,))
    if cur.fetchone():
        return False, "A semester with this name already exists."
    cur.execute("SELECT COUNT(*) FROM semesters")
    first = cur.fetchone()[0] == 0
    cur.execute("INSERT INTO semesters (name, start_date, end_date, is_active) VALUES (%s,%s,%s,%s)",
                (name, start, end, 1 if first else 0))
    conn.commit()
    return True, f"Semester '{name}' created" + (" and set active." if first else ".")


def list_semesters(conn):
    cur = conn.cursor()
    cur.execute("SELECT semester_id, name, start_date, end_date, is_active "
                "FROM semesters ORDER BY start_date DESC")
    return [dict(id=r[0], name=r[1], start=r[2], end=r[3], active=bool(r[4]))
            for r in cur.fetchall()]


def active_semester(conn):
    cur = conn.cursor()
    cur.execute("SELECT semester_id, name, start_date, end_date FROM semesters "
                "WHERE is_active = 1 LIMIT 1")
    r = cur.fetchone()
    return dict(id=r[0], name=r[1], start=r[2], end=r[3]) if r else None


def set_active_semester(conn, semester_id):
    cur = conn.cursor()
    cur.execute("UPDATE semesters SET is_active = 0")
    cur.execute("UPDATE semesters SET is_active = 1 WHERE semester_id = %s", (semester_id,))
    conn.commit()


def delete_semester(conn, semester_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM semesters WHERE semester_id = %s", (semester_id,))
    conn.commit()


def semester_text(sem):
    return (f"{sem['name']}  |  {sem['start'].strftime('%d %b %Y')} to "
            f"{sem['end'].strftime('%d %b %Y')}")


# ------------------------------------------------------------- assignments
def sections_for_course(conn, course_id):
    cur = conn.cursor()
    cur.execute("SELECT s.section, COUNT(*) FROM enrollments e "
                "JOIN students s ON s.student_id = e.student_id "
                "WHERE e.course_id = %s GROUP BY s.section ORDER BY s.section", (course_id,))
    return cur.fetchall()


def add_assignment(conn, semester_id, teacher_id, course_id, section):
    cur = conn.cursor()
    cur.execute("INSERT INTO teacher_courses (semester_id, teacher_id, course_id, section) "
                "VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE teacher_id = %s",
                (semester_id, teacher_id, course_id, section, teacher_id))
    conn.commit()


def remove_assignment(conn, assignment_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM teacher_courses WHERE id = %s", (assignment_id,))
    conn.commit()


def clear_assignments(conn, semester_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM teacher_courses WHERE semester_id = %s", (semester_id,))
    conn.commit()


def list_assignments(conn, semester_id, text=""):
    cur = conn.cursor()
    cur.execute(
        "SELECT a.id, t.teacher_id, t.name, c.course_code, c.course_name, a.section, "
        "       (SELECT COUNT(*) FROM enrollments e JOIN students s ON s.student_id = e.student_id "
        "         WHERE e.course_id = a.course_id AND s.section = a.section) "
        "FROM teacher_courses a JOIN teachers t ON t.teacher_id = a.teacher_id "
        "JOIN courses c ON c.course_id = a.course_id "
        "WHERE a.semester_id = %s ORDER BY t.teacher_id, c.course_code, a.section", (semester_id,))
    rows = [dict(id=r[0], teacher_id=r[1], teacher=r[2], code=r[3], course=r[4],
                 section=r[5], size=r[6]) for r in cur.fetchall()]
    text = text.strip().lower()
    if text:
        rows = [r for r in rows if text in r["teacher"].lower() or text in r["code"].lower()
                or text in r["course"].lower() or text == r["section"].lower()
                or text == str(r["teacher_id"])]
    return rows


def auto_assign(conn, semester_id):
    """Give a teacher to every course + section that has none. Returns how many were added."""
    cur = conn.cursor()
    cur.execute("SELECT t.teacher_id, t.name, COALESCE(d.dept_code,'') FROM teachers t "
                "LEFT JOIN departments d ON d.dept_id = t.dept_id ORDER BY t.teacher_id")
    teachers = cur.fetchall()
    if not teachers:
        return 0
    cur.execute("SELECT c.course_id, c.course_code, c.course_name, COALESCE(d.dept_code,'') "
                "FROM courses c LEFT JOIN departments d ON d.dept_id = c.dept_id")
    courses = {r[0]: r for r in cur.fetchall()}
    cur.execute("SELECT e.course_id, s.section FROM enrollments e "
                "JOIN students s ON s.student_id = e.student_id GROUP BY e.course_id, s.section")
    pairs = sorted(cur.fetchall(), key=lambda p: (courses[p[0]][1], p[1]))
    cur.execute("SELECT teacher_id, course_id, section FROM teacher_courses WHERE semester_id=%s",
                (semester_id,))
    load = defaultdict(int)
    done = set()
    for tid, cid, sec in cur.fetchall():
        load[tid] += 1
        done.add((cid, sec))

    preferred = {}
    for cid, (_, code, name, dept) in courses.items():
        match = [t[0] for t in teachers
                 if t[2] and (t[2].lower() in name.lower() or t[2].lower() == dept.lower())]
        preferred[cid] = match or [t[0] for t in teachers]

    rows = []
    for cid, sec in pairs:
        if (cid, sec) in done:
            continue
        tid = min(preferred[cid], key=lambda t: (load[t], t))
        lowest = min(load[t[0]] for t in teachers)
        if load[tid] > lowest + 1:                   # keep the workload fair for everybody
            tid = min((t[0] for t in teachers), key=lambda t: (load[t], t))
        load[tid] += 1
        rows.append((semester_id, tid, cid, sec))
    cur.executemany("INSERT INTO teacher_courses (semester_id, teacher_id, course_id, section) "
                    "VALUES (%s,%s,%s,%s)", rows)
    conn.commit()
    return len(rows)


# ------------------------------------------------------------------- views
def _t(td):
    secs = int(td.total_seconds())
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}"


def student_timetable(conn, student_id, semester_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT cr.weekday, cr.period_no, cr.start_time, cr.end_time, c.course_code, c.course_name, "
        "       t.name, b.building_no, r.room_no "
        "FROM students s "
        "JOIN enrollments e ON e.student_id = s.student_id "
        "JOIN teacher_courses a ON a.course_id = e.course_id AND a.section = s.section "
        "     AND a.semester_id = %s "
        "JOIN class_routine cr ON cr.assignment_id = a.id "
        "JOIN courses c ON c.course_id = a.course_id "
        "JOIN teachers t ON t.teacher_id = a.teacher_id "
        "JOIN rooms r ON r.room_id = cr.room_id JOIN buildings b ON b.building_id = r.building_id "
        "WHERE s.student_id = %s ORDER BY cr.weekday, cr.period_no", (semester_id, student_id))
    return [dict(day=r[0], period=r[1], start=_t(r[2]), end=_t(r[3]), code=r[4], course=r[5],
                 teacher=r[6], room=f"{r[7]}-{r[8]}") for r in cur.fetchall()]


def student_courses(conn, student_id, semester_id):
    """Every course of the student with the teacher (None if not assigned yet)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT c.course_id, c.course_code, c.course_name, t.name "
        "FROM students s JOIN enrollments e ON e.student_id = s.student_id "
        "JOIN courses c ON c.course_id = e.course_id "
        "LEFT JOIN teacher_courses a ON a.course_id = e.course_id AND a.section = s.section "
        "     AND a.semester_id = %s "
        "LEFT JOIN teachers t ON t.teacher_id = a.teacher_id "
        "WHERE s.student_id = %s ORDER BY c.course_code", (semester_id, student_id))
    return [dict(course_id=r[0], code=r[1], course=r[2], teacher=r[3]) for r in cur.fetchall()]


def student_marks(conn, student_id, semester_id):
    cur = conn.cursor()
    cur.execute("SELECT course_id, marks FROM marks WHERE semester_id=%s AND student_id=%s",
                (semester_id, student_id))
    return {r[0]: float(r[1]) for r in cur.fetchall()}


def teacher_assignments(conn, teacher_id, semester_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT a.id, a.course_id, c.course_code, c.course_name, a.section, "
        "       COALESCE(d.dept_code,''), "
        "       (SELECT COUNT(*) FROM enrollments e JOIN students s ON s.student_id = e.student_id "
        "         WHERE e.course_id = a.course_id AND s.section = a.section) "
        "FROM teacher_courses a JOIN courses c ON c.course_id = a.course_id "
        "LEFT JOIN departments d ON d.dept_id = c.dept_id "
        "WHERE a.teacher_id = %s AND a.semester_id = %s ORDER BY c.course_code, a.section",
        (teacher_id, semester_id))
    return [dict(id=r[0], course_id=r[1], code=r[2], course=r[3], section=r[4],
                 klass=r[5], size=r[6]) for r in cur.fetchall()]


def teacher_timetable(conn, teacher_id, semester_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT cr.weekday, cr.period_no, cr.start_time, cr.end_time, c.course_code, c.course_name, "
        "       a.section, b.building_no, r.room_no, a.id "
        "FROM teacher_courses a JOIN class_routine cr ON cr.assignment_id = a.id "
        "JOIN courses c ON c.course_id = a.course_id "
        "JOIN rooms r ON r.room_id = cr.room_id JOIN buildings b ON b.building_id = r.building_id "
        "WHERE a.teacher_id = %s AND a.semester_id = %s ORDER BY cr.weekday, cr.period_no",
        (teacher_id, semester_id))
    return [dict(day=r[0], period=r[1], start=_t(r[2]), end=_t(r[3]), code=r[4], course=r[5],
                 section=r[6], room=f"{r[7]}-{r[8]}", assignment=r[9]) for r in cur.fetchall()]


def assignment_exam_rooms(conn, course_id, section):
    """Exam date, time and the rooms where this section's students sit."""
    cur = conn.cursor()
    cur.execute(
        "SELECT er.exam_date, ts.start_time, ts.end_time, b.building_no, r.room_no, "
        "       COUNT(*), MIN(sp.seat_no), MAX(sp.seat_no) "
        "FROM exams e JOIN exam_rooms er ON er.exam_id = e.exam_id "
        "JOIN seat_plan sp ON sp.exam_room_id = er.id "
        "JOIN students s ON s.student_id = sp.student_id AND s.section = %s "
        "JOIN rooms r ON r.room_id = er.room_id JOIN buildings b ON b.building_id = r.building_id "
        "JOIN time_slots ts ON ts.slot_id = er.slot_id "
        "WHERE e.course_id = %s "
        "GROUP BY er.id, er.exam_date, ts.start_time, ts.end_time, b.building_no, r.room_no "
        "ORDER BY er.exam_date", (section, course_id))
    return [dict(date=r[0], start=_t(r[1]), end=_t(r[2]), room=f"{r[3]}-{r[4]}",
                 students=r[5], first=r[6], last=r[7]) for r in cur.fetchall()]


def section_timetable(conn, klass, section, semester_id):
    """Weekly timetable of one class (department code) + section, for the admin preview."""
    cur = conn.cursor()
    cur.execute(
        "SELECT cr.weekday, cr.period_no, cr.start_time, cr.end_time, c.course_code, c.course_name, "
        "       t.name, b.building_no, r.room_no "
        "FROM teacher_courses a JOIN class_routine cr ON cr.assignment_id = a.id "
        "JOIN courses c ON c.course_id = a.course_id "
        "JOIN departments d ON d.dept_id = c.dept_id "
        "JOIN teachers t ON t.teacher_id = a.teacher_id "
        "JOIN rooms r ON r.room_id = cr.room_id JOIN buildings b ON b.building_id = r.building_id "
        "WHERE a.semester_id = %s AND d.dept_code = %s AND a.section = %s "
        "ORDER BY cr.weekday, cr.period_no", (semester_id, klass, section))
    return [dict(day=r[0], period=r[1], start=_t(r[2]), end=_t(r[3]), code=r[4], course=r[5],
                 teacher=r[6], room=f"{r[7]}-{r[8]}") for r in cur.fetchall()]


def class_and_sections(conn):
    """[(dept_code, [sections])] for the admin preview boxes."""
    cur = conn.cursor()
    cur.execute("SELECT d.dept_code, s.section FROM students s JOIN departments d "
                "ON d.dept_id = s.dept_id GROUP BY d.dept_code, s.section ORDER BY 1, 2")
    out = defaultdict(list)
    for dept, sec in cur.fetchall():
        out[dept].append(sec)
    return dict(out)


# ------------------------------------------------------------------- marks
def grade_for(marks, max_marks):
    """Bangladesh style letter grade from the percentage."""
    p = marks * 100.0 / max_marks if max_marks else 0
    for limit, letter in ((80, "A+"), (70, "A"), (60, "A-"), (50, "B"), (40, "C"), (33, "D")):
        if p >= limit:
            return letter
    return "F"


def marks_roster(conn, semester_id, course_id, section):
    cur = conn.cursor()
    cur.execute(
        "SELECT s.student_id, s.name, m.marks FROM enrollments e "
        "JOIN students s ON s.student_id = e.student_id AND s.section = %s "
        "LEFT JOIN marks m ON m.student_id = s.student_id AND m.course_id = e.course_id "
        "     AND m.semester_id = %s "
        "WHERE e.course_id = %s ORDER BY s.student_id", (section, semester_id, course_id))
    return [dict(student_id=r[0], name=r[1], marks=None if r[2] is None else float(r[2]))
            for r in cur.fetchall()]


def save_marks(conn, semester_id, teacher_id, assignment_id, entries, max_marks):
    """entries = [(student_id, text)]. Empty text = no marks. Returns (ok, message)."""
    cur = conn.cursor()
    cur.execute("SELECT course_id, section FROM teacher_courses "
                "WHERE id=%s AND teacher_id=%s AND semester_id=%s",
                (assignment_id, teacher_id, semester_id))
    r = cur.fetchone()
    if not r:
        return False, "This course is not assigned to you."
    course_id, section = r
    cur.execute("SELECT s.student_id FROM enrollments e JOIN students s "
                "ON s.student_id = e.student_id AND s.section = %s WHERE e.course_id = %s",
                (section, course_id))
    valid = {x[0] for x in cur.fetchall()}
    rows, deletes = [], []
    for sid, text in entries:
        text = str(text).strip()
        if sid not in valid:
            continue
        if text == "":
            deletes.append(sid)
            continue
        try:
            value = float(text)
        except ValueError:
            return False, f"Marks for {sid} must be a number."
        if value < 0 or value > max_marks:
            return False, f"Marks for {sid} must be between 0 and {max_marks}."
        rows.append((semester_id, sid, course_id, value, teacher_id))
    for r in rows:
        cur.execute(
            "INSERT INTO marks (semester_id, student_id, course_id, marks, updated_by) "
            "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE marks=%s, updated_by=%s",
            r + (r[3], r[4]))
    cur.executemany("DELETE FROM marks WHERE semester_id=%s AND student_id=%s AND course_id=%s",
                    [(semester_id, sid, course_id) for sid in deletes])
    conn.commit()
    return True, f"Saved marks for {len(rows)} student(s)."
