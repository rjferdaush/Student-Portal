"""Part 5: Room Allocation + Seat Plan
For every exam (date + slot) it chooses real rooms and gives each student a
room and a seat number.

Rules:
  - One room = one course in a time slot.
  - Room capacity is never exceeded.
  - A course that needs more than one room tries to stay in one building.
"""
from collections import defaultdict

from db import get_connection

CREATE_SEAT_PLAN = """
CREATE TABLE IF NOT EXISTS seat_plan (
  id INT AUTO_INCREMENT PRIMARY KEY,
  exam_room_id INT NOT NULL,
  student_id VARCHAR(20) NOT NULL,
  seat_no INT NOT NULL,
  UNIQUE (exam_room_id, seat_no),
  UNIQUE (exam_room_id, student_id),
  FOREIGN KEY (exam_room_id) REFERENCES exam_rooms(id),
  FOREIGN KEY (student_id) REFERENCES students(student_id)
)
"""


# ---------- Step 1: load data ----------
def load_data(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT e.exam_id, c.course_code, e.exam_date, e.slot_id, e.course_id "
        "FROM exams e JOIN courses c ON c.course_id = e.course_id "
        "WHERE e.exam_date IS NOT NULL ORDER BY e.exam_date, e.slot_id, c.course_code")
    exams = [dict(exam_id=r[0], code=r[1], date=r[2], slot=r[3], course_id=r[4])
             for r in cur.fetchall()]
    cur.execute(
        "SELECT r.room_id, b.building_no, r.room_no, r.capacity "
        "FROM rooms r JOIN buildings b ON b.building_id = r.building_id")
    rooms = [dict(room_id=r[0], building=r[1], room_no=r[2], capacity=r[3])
             for r in cur.fetchall()]
    cur.execute("SELECT course_id, student_id FROM enrollments ORDER BY student_id")
    students = defaultdict(list)
    for course_id, student_id in cur.fetchall():
        students[course_id].append(student_id)
    return exams, rooms, students


# ---------- Step 2: choose rooms for one course ----------
def pick_rooms(free, size):
    """free = list of room dicts that are still empty. Returns chosen rooms or None."""
    fits = [r for r in free if r["capacity"] >= size]
    if fits:                                            # smallest single room that fits
        return [min(fits, key=lambda r: (r["capacity"], r["building"], r["room_no"]))]

    best = None                                         # try to stay in one building
    for b in sorted({r["building"] for r in free}):
        in_b = sorted([r for r in free if r["building"] == b],
                      key=lambda r: -r["capacity"])
        chosen, total = [], 0
        for r in in_b:
            chosen.append(r)
            total += r["capacity"]
            if total >= size:
                key = (len(chosen), total - size)
                if best is None or key < best[0]:
                    best = (key, chosen)
                break
    if best:
        return best[1]

    chosen, total = [], 0                               # spread over buildings
    for r in sorted(free, key=lambda r: -r["capacity"]):
        chosen.append(r)
        total += r["capacity"]
        if total >= size:
            return chosen
    return None


def allocate_slot(courses, rooms):
    """courses = [(code, size)], rooms = all rooms. Returns {code: [rooms]}."""
    free = list(rooms)
    result = {}
    for code, size in sorted(courses, key=lambda x: -x[1]):   # big courses first
        chosen = pick_rooms(free, size)
        if chosen is None:
            raise RuntimeError(f"No rooms left for {code} ({size} students) in this slot")
        for r in chosen:
            free.remove(r)
        result[code] = chosen
    return result


# ---------- Step 3: seats ----------
def assign_seats(student_ids, chosen_rooms):
    """Fill rooms one by one. Returns [(room, student_id, seat_no)]."""
    seats, i = [], 0
    for room in sorted(chosen_rooms, key=lambda r: (r["building"], r["room_no"])):
        for seat_no in range(1, room["capacity"] + 1):
            if i >= len(student_ids):
                break
            seats.append((room, student_ids[i], seat_no))
            i += 1
    return seats


# ---------- Step 4: save ----------
def save(conn, plan):
    cur = conn.cursor()
    cur.execute(CREATE_SEAT_PLAN)
    cur.execute("DELETE FROM seat_plan")        # old room plan is replaced
    cur.execute("DELETE FROM invigilations")
    cur.execute("DELETE FROM exam_rooms")
    for exam, seats in plan:
        by_room = defaultdict(list)
        for room, student_id, seat_no in seats:
            by_room[room["room_id"]].append((student_id, seat_no))
        for room_id, items in by_room.items():
            cur.execute(
                "INSERT INTO exam_rooms (exam_id, room_id, exam_date, slot_id) "
                "VALUES (%s,%s,%s,%s)",
                (exam["exam_id"], room_id, exam["date"], exam["slot"]))
            er_id = cur.lastrowid
            cur.executemany(
                "INSERT INTO seat_plan (exam_room_id, student_id, seat_no) VALUES (%s,%s,%s)",
                [(er_id, s, n) for s, n in items])
    conn.commit()


def main():
    conn = get_connection()
    try:
        exams, rooms, students = load_data(conn)
        if not exams:
            print("No exams found. Run scheduler.py first.")
            return

        groups = defaultdict(list)
        for e in exams:
            groups[(e["date"], e["slot"])].append(e)

        plan = []
        print("\n=== ROOM ALLOCATION ===")
        print(f"{'Date':<12}{'Slot':<6}{'Course':<9}{'Students':<10}Rooms (building-room: seats used/capacity)")
        for (d, s), group in sorted(groups.items()):
            sizes = [(e["code"], len(students[e["course_id"]])) for e in group]
            alloc = allocate_slot(sizes, rooms)
            for e in sorted(group, key=lambda x: x["code"]):
                ids = students[e["course_id"]]
                seats = assign_seats(ids, alloc[e["code"]])
                assert len(seats) == len(ids), "some student has no seat"
                plan.append((e, seats))
                used = defaultdict(int)
                for room, _, _ in seats:
                    used[room["room_id"]] += 1
                txt = ", ".join(f"{r['building']}-{r['room_no']}: {used[r['room_id']]}/{r['capacity']}"
                                for r in sorted(alloc[e["code"]],
                                                key=lambda r: (r["building"], r["room_no"])))
                print(f"{d.isoformat():<12}{s:<6}{e['code']:<9}{len(ids):<10}{txt}")

        save(conn, plan)
        print("\nRoom allocation and seat plan saved (tables: exam_rooms, seat_plan).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
