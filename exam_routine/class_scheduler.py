"""Class routine generator (weekly timetable).

For the active semester it places every course + section class (classes_per_week times)
into a day, a period and a room.

Rules:
  - A teacher is never in two classes at the same day and period.
  - A student (section) never has two classes at the same day and period.
  - A room holds one class at a time and must be big enough for the section.
  - The same course + section is not placed twice on the same day when possible.
  - A section tries to keep the same room (home room).
Class days, period times and classes per week come from the admin's Time settings.
"""
from collections import defaultdict

import academic
from db import get_connection


def load_inputs(conn, semester_id):
    cur = conn.cursor()
    cur.execute("SELECT id, teacher_id, course_id, section FROM teacher_courses "
                "WHERE semester_id = %s ORDER BY id", (semester_id,))
    assignments = {r[0]: dict(id=r[0], teacher=r[1], course=r[2], section=r[3]) for r in cur.fetchall()}
    cur.execute(
        "SELECT a.id, e.student_id FROM teacher_courses a "
        "JOIN enrollments e ON e.course_id = a.course_id "
        "JOIN students s ON s.student_id = e.student_id AND s.section = a.section "
        "WHERE a.semester_id = %s", (semester_id,))
    students = defaultdict(set)
    for aid, sid in cur.fetchall():
        students[aid].add(sid)
    cur.execute("SELECT room_id, capacity FROM rooms ORDER BY capacity, room_id")
    rooms = cur.fetchall()
    return assignments, students, rooms


def build_plan(assignments, students, rooms, days, periods, per_week):
    """Returns (meetings, unplaced). meetings = [(assignment_id, day, period_no, room_id)]."""
    size = {a: len(students[a]) for a in assignments}
    by_student = defaultdict(list)
    for aid, sids in students.items():
        for sid in sids:
            by_student[sid].append(aid)
    conflicts = defaultdict(set)
    for lst in by_student.values():
        group = set(lst)
        for a in lst:
            conflicts[a] |= group
    for a in assignments:
        conflicts[a].discard(a)

    slots = [(d, p) for d in days for p in range(1, len(periods) + 1)]
    placed_at = defaultdict(set)          # slot -> assignment ids
    teacher_busy = set()                  # (teacher, day, period)
    room_busy = set()                     # (room, day, period)
    load = defaultdict(int)               # slot -> number of classes
    used_days = defaultdict(set)          # assignment -> days already used
    day_load = defaultdict(int)           # (section key, day) -> classes of that section
    home = {}                             # clique key -> room id
    meetings, unplaced = [], []

    order = sorted(assignments, key=lambda a: (-len(conflicts[a]), -size[a], a))
    for rep in range(per_week):
        for a in order:
            info = assignments[a]
            key = min(conflicts[a] | {a})
            best = None
            for slot in slots:
                d, p = slot
                if d in used_days[a] and len(days) >= per_week:
                    continue
                if (info["teacher"], d, p) in teacher_busy:
                    continue
                if conflicts[a] & placed_at[slot]:
                    continue
                free = [rid for rid, cap in rooms if cap >= size[a] and (rid, d, p) not in room_busy]
                if not free:
                    continue
                score = (day_load[(key, d)], load[slot], days.index(d), p)
                if best is None or score < best[0]:
                    pick = home.get(key) if home.get(key) in free else free[0]
                    best = (score, slot, pick)
            if best is None:
                unplaced.append(a)
                continue
            _, (d, p), room = best
            placed_at[(d, p)].add(a)
            teacher_busy.add((info["teacher"], d, p))
            room_busy.add((room, d, p))
            load[(d, p)] += 1
            used_days[a].add(d)
            day_load[(key, d)] += 1
            home.setdefault(key, room)
            meetings.append((a, d, p, room))
    return meetings, unplaced


def verify(assignments, students, rooms, meetings):
    """Independent check of all rules. Returns a list of problems (empty = fine)."""
    cap = dict(rooms)
    errors = []
    teacher_slot, room_slot, student_slot = set(), set(), set()
    for a, d, p, room in meetings:
        t = assignments[a]["teacher"]
        if (t, d, p) in teacher_slot:
            errors.append(f"teacher {t} double booked on day {d} period {p}")
        teacher_slot.add((t, d, p))
        if (room, d, p) in room_slot:
            errors.append(f"room {room} double booked on day {d} period {p}")
        room_slot.add((room, d, p))
        if cap[room] < len(students[a]):
            errors.append(f"room {room} is too small for assignment {a}")
        for sid in students[a]:
            if (sid, d, p) in student_slot:
                errors.append(f"student {sid} has two classes on day {d} period {p}")
                break
            student_slot.add((sid, d, p))
    return errors


def generate(conn, semester_id):
    """Build and save the class routine. Returns (placed_count, unplaced_count, message)."""
    settings = academic.get_settings(conn)
    periods = academic.class_periods(settings)
    days = academic.parse_days(settings["class_days"])
    per_week = int(settings["classes_per_week"])
    if not days:
        return 0, 0, "Choose at least one class day in Time settings."
    assignments, students, rooms = load_inputs(conn, semester_id)
    if not assignments:
        return 0, 0, "No teacher is assigned yet. Assign courses to teachers first."
    if not rooms:
        return 0, 0, "No rooms found. Import the CSV data first."
    meetings, unplaced = build_plan(assignments, students, rooms, days, periods, per_week)
    problems = verify(assignments, students, rooms, meetings)
    if problems:
        return 0, len(unplaced), "Internal check failed: " + problems[0]
    times = {no: (a, b) for no, a, b in periods}
    cur = conn.cursor()
    cur.execute("DELETE FROM class_routine WHERE semester_id = %s", (semester_id,))
    cur.executemany(
        "INSERT INTO class_routine (semester_id, assignment_id, weekday, period_no, "
        "start_time, end_time, room_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        [(semester_id, a, d, p, times[p][0], times[p][1], room) for a, d, p, room in meetings])
    conn.commit()
    msg = f"Placed {len(meetings)} classes."
    if unplaced:
        msg += (f" {len(unplaced)} class(es) could not be placed. Add more periods, days or "
                f"rooms, or reduce classes per week.")
    return len(meetings), len(unplaced), msg


def main():
    conn = get_connection()
    try:
        sem = academic.active_semester(conn)
        if not sem:
            print("No active semester. Create one first.")
            return
        print(f"Semester: {academic.semester_text(sem)}")
        print(generate(conn, sem["id"])[2])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
