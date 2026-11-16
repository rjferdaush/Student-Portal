"""Read-only queries used by the student, teacher and admin screens."""


def fmt_time(td):
    secs = int(td.total_seconds())
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}"


def student_info(conn, student_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT s.name, d.dept_code, s.section, s.intake "
        "FROM students s JOIN departments d ON d.dept_id = s.dept_id "
        "WHERE s.student_id = %s", (student_id,))
    r = cur.fetchone()
    return dict(name=r[0], dept=r[1], section=r[2], intake=r[3]) if r else None


def student_exams(conn, student_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT er.exam_date, ts.start_time, ts.end_time, c.course_code, c.course_name, "
        "       b.building_no, r.room_no, sp.seat_no "
        "FROM seat_plan sp "
        "JOIN exam_rooms er ON er.id = sp.exam_room_id "
        "JOIN exams e ON e.exam_id = er.exam_id "
        "JOIN courses c ON c.course_id = e.course_id "
        "JOIN rooms r ON r.room_id = er.room_id "
        "JOIN buildings b ON b.building_id = r.building_id "
        "JOIN time_slots ts ON ts.slot_id = er.slot_id "
        "WHERE sp.student_id = %s ORDER BY er.exam_date, er.slot_id", (student_id,))
    return [dict(date=r[0], start=fmt_time(r[1]), end=fmt_time(r[2]), code=r[3],
                 course=r[4], building=r[5], room=r[6], seat=r[7]) for r in cur.fetchall()]


def teacher_info(conn, teacher_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT t.name, t.rank_type, d.dept_code FROM teachers t "
        "LEFT JOIN departments d ON d.dept_id = t.dept_id WHERE t.teacher_id = %s",
        (int(teacher_id),))
    r = cur.fetchone()
    return dict(name=r[0], rank=r[1], dept=r[2] or "-") if r else None


def teacher_duties(conn, teacher_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT er.exam_date, ts.start_time, ts.end_time, c.course_code, c.course_name, "
        "       b.building_no, r.room_no, "
        "       (SELECT COUNT(*) FROM seat_plan sp WHERE sp.exam_room_id = er.id), "
        "       (SELECT GROUP_CONCAT(t2.name ORDER BY t2.teacher_id SEPARATOR ', ') "
        "          FROM invigilations i2 JOIN teachers t2 ON t2.teacher_id = i2.teacher_id "
        "         WHERE i2.exam_room_id = er.id AND i2.teacher_id <> i.teacher_id) "
        "FROM invigilations i "
        "JOIN exam_rooms er ON er.id = i.exam_room_id "
        "JOIN exams e ON e.exam_id = er.exam_id "
        "JOIN courses c ON c.course_id = e.course_id "
        "JOIN rooms r ON r.room_id = er.room_id "
        "JOIN buildings b ON b.building_id = r.building_id "
        "JOIN time_slots ts ON ts.slot_id = er.slot_id "
        "WHERE i.teacher_id = %s ORDER BY er.exam_date, er.slot_id", (int(teacher_id),))
    return [dict(date=r[0], start=fmt_time(r[1]), end=fmt_time(r[2]), code=r[3],
                 course=r[4], building=r[5], room=r[6], students=r[7],
                 partners=r[8] or "-") for r in cur.fetchall()]


def teacher_list(conn):
    cur = conn.cursor()
    cur.execute("SELECT teacher_id, name, rank_type FROM teachers ORDER BY teacher_id")
    return cur.fetchall()


def counts(conn):
    """Small numbers for the admin dashboard."""
    cur = conn.cursor()
    out = {}
    for key, table in (("students", "students"), ("courses", "courses"),
                       ("teachers", "teachers"), ("rooms", "rooms"),
                       ("exams", "exams"), ("duties", "invigilations")):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            out[key] = cur.fetchone()[0]
        except Exception:
            out[key] = 0
    return out
