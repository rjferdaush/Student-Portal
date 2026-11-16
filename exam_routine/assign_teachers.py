"""Part 6: Teacher (invigilator) Assignment
Gives teachers to every exam room.

How duties are given (round by round):
  Round 1: every junior teacher gets 1 duty, then every senior teacher gets 1 duty.
  Round 2: again every junior gets 1, then every senior gets 1, and so on.
  So the work is shared equally and nobody is left without duty until everyone
  has had a turn.

Rules:
  - The same teacher can NOT guard two rooms in the same date + time slot
    (a busy teacher is skipped and keeps his/her turn for the next duty).
  - Two senior teachers are never put in the same room (a junior is used instead).
  - Every room gets at least MIN_TEACHERS_PER_ROOM teachers; big rooms get more
    (1 teacher for every STUDENTS_PER_TEACHER students).
"""
import math
from collections import defaultdict

from db import get_connection

# ---------- Settings (change these) ----------
ROTATION_ORDER = ["junior", "senior"]   # who goes first inside every round
MIN_TEACHERS_PER_ROOM = 2               # every room gets at least this many teachers
STUDENTS_PER_TEACHER = 30               # and 1 teacher for every 30 students in the room


# ---------- Step 1: load data ----------
def load_data(conn):
    cur = conn.cursor()
    cur.execute("SELECT teacher_id, name, rank_type FROM teachers ORDER BY teacher_id")
    teachers = [dict(id=r[0], name=r[1], rank=r[2]) for r in cur.fetchall()]
    cur.execute(
        "SELECT er.id, er.exam_date, er.slot_id, c.course_code, b.building_no, r.room_no, "
        "       COUNT(sp.id) "
        "FROM exam_rooms er "
        "JOIN exams e ON e.exam_id = er.exam_id "
        "JOIN courses c ON c.course_id = e.course_id "
        "JOIN rooms r ON r.room_id = er.room_id "
        "JOIN buildings b ON b.building_id = r.building_id "
        "LEFT JOIN seat_plan sp ON sp.exam_room_id = er.id "
        "GROUP BY er.id, er.exam_date, er.slot_id, c.course_code, b.building_no, r.room_no "
        "ORDER BY er.exam_date, er.slot_id, b.building_no, r.room_no")
    rooms = [dict(id=r[0], date=r[1], slot=r[2], course=r[3],
                  place=f"{r[4]}-{r[5]}", students=r[6]) for r in cur.fetchall()]
    return teachers, rooms


# ---------- Step 2: teachers needed in a room ----------
def teachers_needed(n_students):
    return max(MIN_TEACHERS_PER_ROOM, math.ceil(n_students / STUDENTS_PER_TEACHER))


# ---------- Step 3: the rotation list ----------
def build_cycle(teachers):
    """All juniors first, then all seniors. This list is used again and again."""
    cycle = []
    for rank in ROTATION_ORDER:
        cycle += sorted([t for t in teachers if t["rank"] == rank], key=lambda t: t["id"])
    cycle += [t for t in teachers if t not in cycle]
    return cycle


def assign_slot(rooms, cycle, duty):
    """rooms = rooms of ONE date+slot. duty = {teacher_id: duties so far}.
    Returns (assignment, forced) where forced = rooms that had to get 2 seniors.

    1) Pick the teachers with the fewest duties (juniors first when equal),
       but never more seniors than rooms (max 1 senior per room).
    2) Give every room one senior (if any), then fill the rest with juniors.
    """
    needs = {r["id"]: teachers_needed(r["students"]) for r in rooms}
    total = sum(needs.values())
    if total > len(cycle):
        raise RuntimeError(
            f"Not enough teachers on {rooms[0]['date']} slot {rooms[0]['slot']}: "
            f"need {total}, have {len(cycle)}")

    order = {t["id"]: i for i, t in enumerate(cycle)}      # juniors first, then seniors
    ranked = sorted(cycle, key=lambda t: (duty[t["id"]], order[t["id"]]))

    chosen, senior_count = [], 0
    for t in ranked:
        if len(chosen) == total:
            break
        if t["rank"] == "senior":
            if senior_count >= len(rooms):                 # max 1 senior per room
                continue
            senior_count += 1
        chosen.append(t)
    if len(chosen) < total:                                # not enough juniors: use extra seniors
        for t in ranked:
            if len(chosen) == total:
                break
            if t not in chosen:
                chosen.append(t)

    seniors = [t for t in chosen if t["rank"] == "senior"]
    juniors = [t for t in chosen if t["rank"] != "senior"]
    result = {r["id"]: [] for r in rooms}
    by_need = sorted(rooms, key=lambda r: -needs[r["id"]])
    for r in by_need:                                      # one senior in every room first
        if seniors:
            result[r["id"]].append(seniors.pop(0))
    for r in by_need:                                      # then juniors
        while len(result[r["id"]]) < needs[r["id"]] and juniors:
            result[r["id"]].append(juniors.pop(0))
    forced = 0
    for r in by_need:                                      # leftover seniors (rare)
        while len(result[r["id"]]) < needs[r["id"]] and seniors:
            result[r["id"]].append(seniors.pop(0))
    for r in rooms:
        if sum(t["rank"] == "senior" for t in result[r["id"]]) > 1:
            forced += 1
        result[r["id"]].sort(key=lambda t: t["rank"] == "senior")   # juniors first, senior last
        for t in result[r["id"]]:
            duty[t["id"]] += 1
    return result, forced


# ---------- Step 4: save ----------
def save(conn, rows):
    cur = conn.cursor()
    cur.execute("DELETE FROM invigilations")   # old duty list is replaced
    cur.executemany(
        "INSERT INTO invigilations (exam_room_id, teacher_id, exam_date, slot_id) "
        "VALUES (%s,%s,%s,%s)", rows)
    conn.commit()


def main():
    conn = get_connection()
    try:
        try:
            teachers, rooms = load_data(conn)
        except Exception as e:
            print("Could not read rooms/seat plan. Run allocate_rooms.py first.")
            print("Details:", e)
            return
        if not rooms:
            print("No exam rooms found. Run scheduler.py and allocate_rooms.py first.")
            return

        groups = defaultdict(list)
        for r in rooms:
            groups[(r["date"], r["slot"])].append(r)

        cycle = build_cycle(teachers)
        duty = defaultdict(int)
        forced_total = 0
        rows, shown = [], []
        for (d, s), group in sorted(groups.items()):
            assigned, forced = assign_slot(group, cycle, duty)
            forced_total += forced
            ids = [t["id"] for ts in assigned.values() for t in ts]
            assert len(ids) == len(set(ids)), "a teacher was used twice in one slot"
            for room in group:
                names = ", ".join(f"{t['name']} ({t['rank'][0].upper()})"
                                  for t in assigned[room["id"]])
                shown.append((d, s, room, names))
                for t in assigned[room["id"]]:
                    rows.append((room["id"], t["id"], d, s))

        print("\n=== TEACHER DUTY ===")
        print(f"{'Date':<12}{'Slot':<6}{'Course':<9}{'Room':<9}{'Students':<10}Teachers (S=senior, J=junior)")
        for d, s, room, names in shown:
            print(f"{d.isoformat():<12}{s:<6}{room['course']:<9}{room['place']:<9}"
                  f"{room['students']:<10}{names}")

        print("\n=== Duties per teacher ===")
        for t in cycle:
            print(f"  {t['name']:<16}{t['rank']:<8}{duty[t['id']]} duties")
        counts = [duty[t["id"]] for t in teachers]
        print(f"\nFewest duties: {min(counts)}, most duties: {max(counts)}")
        if forced_total:
            print(f"Warning: {forced_total} room(s) had two senior teachers "
                  f"because no junior teacher was free.")

        save(conn, rows)
        print("Duty list saved to the 'invigilations' table.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
