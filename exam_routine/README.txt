EXAM ROUTINE SYSTEM
===================

1. Start MySQL in XAMPP Control Panel.
2. Install the libraries (once):
       python -m pip install -r requirements.txt
3. Run the app:
       python app.py

Order of work for the admin (first time):
  1. Admin > Register (set admin password) > Login.
  2. Routine tools:  Import data (choose data/ or demo_school/ folder).
  3. Semesters:      Create a semester (name, start date, end date). The first one is active.
  4. Time settings:  Exam time, exam days, class time, class days, classes per week, total marks.
  5. Assign courses: Give each teacher courses and sections for the semester
                     (manually, or "Auto-assign all unassigned").
  6. Class routine:  Generate class routine (weekly timetable with rooms and times).
  7. Routine tools:  Generate exam routine (first exam date).
  8. Teacher IDs tab: give every teacher their ID.

Teachers: choose Teacher > Register (first time only) with the teacher ID and a password.
  They see their courses, class routine, enter marks, see the exam routine of their
  sections and their exam duty.
Students: choose Student > Register (first time only) with the student ID and a password.
  They see exam routine, class routine, courses with teacher and room, and marks.

If your MySQL has a password, write it in config.py (DB_PASSWORD = "your password").

Data sets included:
  data/         small demo (50 students, 6 courses)
  demo_school/  classes 6 to 10, 10 sections per class, 70 students per section,
                8 subjects per class, 80 junior + 50 senior teachers, 30 rooms
Keep "Delete old data first" ticked when you import a different data set.

Command-line tools (optional): run_all.py, conflict_checker.py, scheduler.py,
allocate_rooms.py, assign_teachers.py, class_scheduler.py
