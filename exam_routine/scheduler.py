"""Part 4: Scheduler
Gives every course an exam date and a time slot.

Rules used here:
  - A student can have only ONE exam per day, so two courses that share a
    student must go on different days (conflict graph from Part 3).
  - Exams are held only on EXAM_WEEKDAYS (Fri, Sat and the gap days are off).
  - Each day has the time slots from the time_slots table (4 slots).
  - One room = one course in a slot, and a course needs enough room capacity
    (a big course may use more than one room).
Teachers are handled later in Part 6.
"""
from collections import defaultdict
from datetime import date, timedelta

from db import get_connection
from conflict_checker import load_enrollments, build_conflicts

# ---------- Settings (change these) ----------
START_DATE = date(2026, 11, 8)      # first possible exam date
EXAM_WEEKDAYS = {6, 1, 3}           # Python weekday: Mon=0 ... Sun=6  -> Sun, Tue, Thu
MAX_EXAM_DAYS = 60                  # safety limit


# ---------- Step 1: helpers ----------
def make_exam_dates(start, weekdays, count):
    dates, d = [], start
    while len(dates) < count:
        if d.weekday() in weekdays:
            dates.append(d)
        d += timedelta(days=1)
    return dates


def fmt_time(td):
    secs = int(td.total_seconds())
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}"


def load_rooms_and_slots(conn):
    cur = conn.cursor()
    cur.execute("SELECT capacity FROM rooms ORDER BY capacity DESC")
    room_caps = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT slot_id, start_time, end_time FROM time_slots ORDER BY slot_id")
    slots = {r[0]: f"{fmt_time(r[1])}-{fmt_time(r[2])}" for r in cur.fetchall()}
    return room_caps, slots


# ---------- Step 2: pick rooms for a course inside one slot ----------
def take_rooms(free, size):
    """free = list of free room capacities. Returns indexes to use, or None."""
    fits = [i for i, c in enumerate(free) if c >= size]
    if fits:                                   # best fit: smallest room that is enough
        return [min(fits, key=lambda i: free[i])]
    chosen, total = [], 0                      # otherwise use the biggest rooms
    for i in sorted(range(len(free)), key=lambda i: -free[i]):
        chosen.append(i)
        total += free[i]
        if total >= size:
            return chosen
    return None


# ---------- Step 3: the scheduler ----------
def schedule(course_size, neighbors, room_caps, slot_ids, num_days):
    day_of, slot_of, rooms_used = {}, {}, {}
    free = {(d, s): list(room_caps) for d in range(num_days) for s in slot_ids}
    remaining = set(course_size)

    def saturation(c):                         # how many different days neighbors already use
        return len({day_of[n] for n in neighbors[c] if n in day_of})

    while remaining:
        # hardest course first (DSATUR idea)
        c = max(sorted(remaining),
                key=lambda x: (saturation(x), len(neighbors[x]), course_size[x]))
        banned = {day_of[n] for n in neighbors[c] if n in day_of}
        placed = False
        for d in range(num_days):
            if d in banned:
                continue
            for s in slot_ids:
                idx = take_rooms(free[(d, s)], course_size[c])
                if idx is not None:
                    for i in sorted(idx, reverse=True):
                        free[(d, s)].pop(i)
                    day_of[c], slot_of[c], rooms_used[c] = d, s, len(idx)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            raise RuntimeError(f"Could not place {c}: not enough room capacity or days")
        remaining.remove(c)
    return day_of, slot_of, rooms_used


# ---------- Step 4: verify the result ----------
def verify(enrollments, day_of):
    by_student = defaultdict(list)
    for student, course in enrollments:
        by_student[student].append(day_of[course])
    errors = []
    for student, days in by_student.items():
        if len(days) != len(set(days)):
            errors.append(f"Student {student} has two exams on the same day")
    return errors


# ---------- Step 5: save to MySQL ----------
def save_schedule(conn, rows):
    cur = conn.cursor()
    cur.execute("SHOW TABLES LIKE 'seat_plan'")  # seat_plan exists after Part 5
    if cur.fetchone():
        cur.execute("DELETE FROM seat_plan")
    cur.execute("DELETE FROM invigilations")   # old routine is replaced
    cur.execute("DELETE FROM exam_rooms")
    cur.execute("DELETE FROM exams")
    cur.execute("SELECT course_code, course_id FROM courses")
    course_id = dict(cur.fetchall())
    cur.executemany(
        "INSERT INTO exams (course_id, exam_date, slot_id) VALUES (%s,%s,%s)",
        [(course_id[c], d, s) for c, d, s in rows])
    conn.commit()


def main():
    conn = get_connection()
    try:
        enrollments = load_enrollments(conn)
        room_caps, slots = load_rooms_and_slots(conn)
        course_size, shared, neighbors = build_conflicts(enrollments)

        dates = make_exam_dates(START_DATE, EXAM_WEEKDAYS, MAX_EXAM_DAYS)
        day_of, slot_of, rooms_used = schedule(
            course_size, neighbors, room_caps, sorted(slots), MAX_EXAM_DAYS)

        errors = verify(enrollments, day_of)
        if errors:
            print("Verification failed:")
            for e in errors:
                print(" -", e)
            return

        print("\n=== EXAM ROUTINE ===")
        print(f"{'Date':<12}{'Day':<5}{'Slot':<6}{'Time':<13}{'Course':<9}{'Students':<10}Rooms")
        order = sorted(course_size, key=lambda c: (day_of[c], slot_of[c], c))
        for c in order:
            d = dates[day_of[c]]
            print(f"{d.isoformat():<12}{d.strftime('%a'):<5}{slot_of[c]:<6}"
                  f"{slots[slot_of[c]]:<13}{c:<9}{course_size[c]:<10}{rooms_used[c]}")

        used_days = sorted({day_of[c] for c in course_size})
        print(f"\nExam days used: {len(used_days)} "
              f"({dates[used_days[0]]} to {dates[used_days[-1]]})")
        print("Check passed: no student has two exams on the same day.")

        save_schedule(conn, [(c, dates[day_of[c]], slot_of[c]) for c in course_size])
        print("Routine saved to the 'exams' table.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
