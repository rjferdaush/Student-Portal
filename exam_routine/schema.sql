CREATE DATABASE IF NOT EXISTS exam_routine CHARACTER SET utf8mb4;
USE exam_routine;

CREATE TABLE IF NOT EXISTS departments (
  dept_id INT AUTO_INCREMENT PRIMARY KEY,
  dept_code VARCHAR(10) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
  student_id VARCHAR(20) PRIMARY KEY,
  name VARCHAR(100),
  dept_id INT NOT NULL,
  section VARCHAR(5),
  intake INT,
  FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);

CREATE TABLE IF NOT EXISTS courses (
  course_id INT AUTO_INCREMENT PRIMARY KEY,
  course_code VARCHAR(20) UNIQUE NOT NULL,
  course_name VARCHAR(150),
  dept_id INT,
  FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
  student_id VARCHAR(20),
  course_id INT,
  PRIMARY KEY (student_id, course_id),
  FOREIGN KEY (student_id) REFERENCES students(student_id),
  FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

CREATE TABLE IF NOT EXISTS teachers (
  teacher_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  dept_id INT,
  rank_type ENUM('senior','junior') DEFAULT 'junior'
);

CREATE TABLE IF NOT EXISTS buildings (
  building_id INT AUTO_INCREMENT PRIMARY KEY,
  building_no VARCHAR(20) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
  room_id INT AUTO_INCREMENT PRIMARY KEY,
  building_id INT NOT NULL,
  room_no VARCHAR(20) NOT NULL,
  capacity INT NOT NULL,
  UNIQUE (building_id, room_no),
  FOREIGN KEY (building_id) REFERENCES buildings(building_id)
);

CREATE TABLE IF NOT EXISTS time_slots (
  slot_id INT PRIMARY KEY,
  start_time TIME,
  end_time TIME
);

CREATE TABLE IF NOT EXISTS exams (
  exam_id INT AUTO_INCREMENT PRIMARY KEY,
  course_id INT UNIQUE NOT NULL,
  exam_date DATE,
  slot_id INT,
  FOREIGN KEY (course_id) REFERENCES courses(course_id),
  FOREIGN KEY (slot_id) REFERENCES time_slots(slot_id)
);

CREATE TABLE IF NOT EXISTS exam_rooms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  exam_id INT NOT NULL,
  room_id INT NOT NULL,
  exam_date DATE NOT NULL,
  slot_id INT NOT NULL,
  UNIQUE (room_id, exam_date, slot_id),
  FOREIGN KEY (exam_id) REFERENCES exams(exam_id),
  FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);

CREATE TABLE IF NOT EXISTS invigilations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  exam_room_id INT NOT NULL,
  teacher_id INT NOT NULL,
  exam_date DATE NOT NULL,
  slot_id INT NOT NULL,
  UNIQUE (teacher_id, exam_date, slot_id),
  FOREIGN KEY (exam_room_id) REFERENCES exam_rooms(id),
  FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
);

INSERT IGNORE INTO time_slots (slot_id, start_time, end_time) VALUES
  (1,'09:00','11:00'), (2,'11:30','13:30'), (3,'14:00','16:00'), (4,'16:30','18:30');
