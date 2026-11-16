"""Part 1 + Part 2 together:
   1) check the CSV files  2) create database and tables  3) load CSV data into MySQL
"""
from pathlib import Path

from db import get_connection
from import_csv import validate, save

SCHEMA = Path(__file__).parent / "schema.sql"


def run_schema(conn):
    """Part 1: run every statement in schema.sql."""
    cur = conn.cursor()
    sql = SCHEMA.read_text(encoding="utf-8")
    for stmt in sql.split(";"):
        if stmt.strip():
            cur.execute(stmt)
    conn.commit()
    cur.execute("SHOW TABLES")
    print(f"Part 1 done: {len(cur.fetchall())} tables created")


def main():
    # validate CSV first: if there is any error, MySQL is not touched
    d, errors = validate()
    if errors:
        print(f"\n{len(errors)} error(s) found. Nothing was saved:\n")
        for e in errors:
            print(" -", e)
        return
    print("CSV files are OK.")

    conn = get_connection(with_database=False)
    try:
        run_schema(conn)                 # Part 1
        print("Part 2: saving data...")
        save(conn, d)                    # Part 2
        print("\nAll done! Part 1 + Part 2 finished.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
