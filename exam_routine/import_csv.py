"""Part 2: read the 5 CSV files, validate them, then save to MySQL."""
import csv
from pathlib import Path
from db import get_connection

DATA = Path(__file__).parent / "data"

FILES = {
    "students":    ["student_id", "name", "dept", "section", "intake"],
    "enrollments": ["student_id", "course_code"],
    "courses":     ["course_code", "course_name", "dept"],
    "teachers":    ["name", "dept", "rank_type"],
    "rooms":       ["building_no", "room_no", "capacity"],
}


# ---------- Step 1: read CSV ----------
def read_csv(name, errors):
    path = DATA / f"{name}.csv"
    if not path.exists():
        errors.append(f"{name}.csv: file not found")
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in FILES[name] if c not in reader.fieldnames]
        if missing:
            errors.append(f"{name}.csv: missing column(s) -> {missing}")
            return []
        rows = []
        for line_no, row in enumerate(reader, start=2):
            clean = {k: (v or "").strip() for k, v in row.items() if k}
            if not any(clean.values()):
                continue  # skip blank lines
            for col in FILES[name]:
                if clean[col] == "":
                    errors.append(f"{name}.csv line {line_no}: '{col}' is empty")
            rows.append((line_no, clean))
        return rows


# ---------- Step 2: validate ----------
def validate():
    errors = []
    d = {n: read_csv(n, errors) for n in FILES}
    if errors:
        return d, errors

    def check_dup(name, key_fn):
        seen = set()
        for ln, r in d[name]:
            k = key_fn(r)
            if k in seen:
                errors.append(f"{name}.csv line {ln}: duplicate {k}")
            seen.add(k)
        return seen

    student_ids = check_dup("students", lambda r: r["student_id"])
    course_codes = check_dup("courses", lambda r: r["course_code"])
    check_dup("rooms", lambda r: (r["building_no"], r["room_no"]))
    check_dup("enrollments", lambda r: (r["student_id"], r["course_code"]))

    for ln, r in d["students"]:
        if not r["intake"].isdigit():
            errors.append(f"students.csv line {ln}: intake must be a number")
    for ln, r in d["rooms"]:
        if not r["capacity"].isdigit() or int(r["capacity"]) <= 0:
            errors.append(f"rooms.csv line {ln}: capacity must be a positive number")
    for ln, r in d["teachers"]:
        if r["rank_type"] not in ("senior", "junior"):
            errors.append(f"teachers.csv line {ln}: rank_type must be senior or junior")
    for ln, r in d["enrollments"]:
        if r["student_id"] not in student_ids:
            errors.append(f"enrollments.csv line {ln}: student {r['student_id']} not in students.csv")
        if r["course_code"] not in course_codes:
            errors.append(f"enrollments.csv line {ln}: course {r['course_code']} not in courses.csv")
    return d, errors


# ---------- Step 3: save to MySQL ----------
def save(conn, d):
    cur = conn.cursor()

    depts = {r["dept"] for n in ("students", "courses", "teachers") for _, r in d[n]}
    cur.executemany("INSERT IGNORE INTO departments (dept_code) VALUES (%s)",
                    [(x,) for x in sorted(depts)])
    cur.execute("SELECT dept_code, dept_id FROM departments")
    dept_id = dict(cur.fetchall())

    blds = {r["building_no"] for _, r in d["rooms"]}
    cur.executemany("INSERT IGNORE INTO buildings (building_no) VALUES (%s)",
                    [(x,) for x in sorted(blds)])
    cur.execute("SELECT building_no, building_id FROM buildings")
    bld_id = dict(cur.fetchall())

    cur.executemany(
        "INSERT IGNORE INTO students (student_id, name, dept_id, section, intake) "
        "VALUES (%s,%s,%s,%s,%s)",
        [(r["student_id"], r["name"], dept_id[r["dept"]], r["section"], int(r["intake"]))
         for _, r in d["students"]])

    cur.executemany(
        "INSERT IGNORE INTO courses (course_code, course_name, dept_id) VALUES (%s,%s,%s)",
        [(r["course_code"], r["course_name"], dept_id[r["dept"]]) for _, r in d["courses"]])

    cur.execute("SELECT name, dept_id FROM teachers")
    existing = set(cur.fetchall())
    new_teachers = [(r["name"], dept_id[r["dept"]], r["rank_type"])
                    for _, r in d["teachers"] if (r["name"], dept_id[r["dept"]]) not in existing]
    cur.executemany("INSERT INTO teachers (name, dept_id, rank_type) VALUES (%s,%s,%s)",
                    new_teachers)

    cur.executemany(
        "INSERT IGNORE INTO rooms (building_id, room_no, capacity) VALUES (%s,%s,%s)",
        [(bld_id[r["building_no"]], r["room_no"], int(r["capacity"])) for _, r in d["rooms"]])

    cur.execute("SELECT course_code, course_id FROM courses")
    course_id = dict(cur.fetchall())
    cur.executemany(
        "INSERT IGNORE INTO enrollments (student_id, course_id) VALUES (%s,%s)",
        [(r["student_id"], course_id[r["course_code"]]) for _, r in d["enrollments"]])

    conn.commit()
    for t in ("students", "enrollments", "courses"):      # fresh statistics keep queries fast
        try:
            cur.execute(f"ANALYZE TABLE {t}")
            cur.fetchall()
        except Exception:
            pass
    for t in ("departments", "buildings", "students", "courses",
              "teachers", "rooms", "enrollments"):
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {cur.fetchone()[0]} rows")


# ---------- Optional: remove all old data ----------
CLEAR_TABLES = ("marks", "class_routine", "teacher_courses", "seat_plan", "invigilations",
                "exam_rooms", "exams", "enrollments",
                "courses", "students", "teachers", "rooms", "buildings", "departments")


def clear_all(conn):
    """Delete all school data (keeps the admin account). Used before importing a new data set."""
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in CLEAR_TABLES:
        try:
            cur.execute(f"TRUNCATE TABLE {table}")
        except Exception:
            pass                                   # table may not exist yet
    try:
        cur.execute("DELETE FROM accounts WHERE role <> 'admin'")
    except Exception:
        pass
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()


def main():
    d, errors = validate()
    if errors:
        print(f"\n{len(errors)} error(s) found. Nothing was saved to MySQL:\n")
        for e in errors:
            print(" -", e)
        return
    print("CSV files are OK. Saving to MySQL...")
    conn = get_connection()
    try:
        save(conn, d)
        print("Done!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
