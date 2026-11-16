"""Part 3: Conflict Checker
Finds which pairs of courses share at least one student
(such courses cannot be scheduled in the same time slot).
"""
from collections import defaultdict
from itertools import combinations

from db import get_connection


# ---------- Step 1: load data from the database ----------
def load_enrollments(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT e.student_id, c.course_code "
        "FROM enrollments e JOIN courses c ON c.course_id = e.course_id"
    )
    return cur.fetchall()


# ---------- Step 2: build the conflict graph ----------
def build_conflicts(enrollments):
    by_student = defaultdict(set)      # student -> set of his/her courses
    course_size = defaultdict(int)     # course -> number of students
    for student_id, course in enrollments:
        by_student[student_id].add(course)
        course_size[course] += 1

    shared = defaultdict(int)          # (courseA, courseB) -> number of common students
    for courses in by_student.values():
        for a, b in combinations(sorted(courses), 2):
            shared[(a, b)] += 1

    neighbors = defaultdict(set)       # course -> courses that cannot share its slot
    for a, b in shared:
        neighbors[a].add(b)
        neighbors[b].add(a)
    return course_size, shared, neighbors


# ---------- Step 3: report ----------
def print_report(course_size, shared, neighbors):
    print("\n=== Students per course ===")
    for c in sorted(course_size):
        print(f"  {c}: {course_size[c]} students")

    print("\n=== Conflicts (same student in two courses) ===")
    if not shared:
        print("  No conflicts")
    for (a, b), n in sorted(shared.items()):
        print(f"  {a} <-> {b} : {n} common students")

    print("\n=== Cannot be in the same slot ===")
    for c in sorted(course_size):
        others = ", ".join(sorted(neighbors[c])) or "(none)"
        print(f"  {c} -> {others}")

    free = sorted(c for c in course_size if not neighbors[c])
    print("\n=== Courses with no conflict (can go in any slot) ===")
    print("  " + (", ".join(free) or "none"))


def main():
    conn = get_connection()
    try:
        data = load_enrollments(conn)
    finally:
        conn.close()
    print(f"Total enrollments: {len(data)}")
    print_report(*build_conflicts(data))


if __name__ == "__main__":
    main()
