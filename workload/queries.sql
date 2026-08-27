-- ============================================================
-- Automatic Index Recommendation — Query Workload
-- ============================================================
-- 40 SQL queries organized by category.
-- Each query has a comment tag like [CATEGORY] that
-- generate_workload.py uses to assign frequencies.
--
-- Categories and their frequency ranges:
--   HIGH_FREQ    → 100-200  (hot-path lookups)
--   SIMPLE_WHERE → 60-90   (single-column filter)
--   COMPOSITE    → 50-75   (multi-condition WHERE)
--   JOIN         → 40-70   (2-3 table joins)
--   JOIN_GROUPBY → 20-40   (aggregation across joins)
--   ORDERBY      → 20-40   (sorting queries)
--   GROUPBY      → 15-35   (standalone aggregation)
--   LOW_FREQ     → 3-10    (rare admin / reporting)
-- ============================================================


-- ============================================================
-- HIGH-FREQUENCY LOOKUPS (hot-path — most impactful for indexing)
-- ============================================================

-- [HIGH_FREQ] Fetch a single student by ID
SELECT * FROM Student WHERE student_id = 42;

-- [HIGH_FREQ] Fetch enrollments for a specific student
SELECT * FROM Enrollment WHERE student_id = 42;

-- [HIGH_FREQ] Fetch attendance records for a specific student
SELECT * FROM Attendance WHERE student_id = 42;

-- [HIGH_FREQ] Fetch a specific course by ID
SELECT * FROM Course WHERE course_id = 10;

-- [HIGH_FREQ] Fetch attendance for a specific student in a specific course
SELECT * FROM Attendance WHERE student_id = 42 AND course_id = 10;


-- ============================================================
-- SIMPLE WHERE (single-column filter)
-- ============================================================

-- [SIMPLE_WHERE] Students in a specific department
SELECT * FROM Student WHERE department = 'Computer Science';

-- [SIMPLE_WHERE] Students in a specific city
SELECT * FROM Student WHERE city = 'Pune';

-- [SIMPLE_WHERE] Students in a specific year
SELECT * FROM Student WHERE year = 3;

-- [SIMPLE_WHERE] Courses in a specific department
SELECT * FROM Course WHERE department = 'Mathematics';

-- [SIMPLE_WHERE] Enrollments in a specific semester
SELECT * FROM Enrollment WHERE semester = 'Fall 2023';

-- [SIMPLE_WHERE] Students who scored above 90
SELECT * FROM Enrollment WHERE marks > 90;

-- [SIMPLE_WHERE] Attendance records below 50%
SELECT * FROM Attendance WHERE percentage < 50;

-- [SIMPLE_WHERE] Students whose name starts with 'A'
SELECT * FROM Student WHERE name LIKE 'A%';


-- ============================================================
-- COMPOSITE WHERE (multi-condition filters)
-- ============================================================

-- [COMPOSITE] Students in CS department from Mumbai
SELECT * FROM Student WHERE department = 'Computer Science' AND city = 'Mumbai';

-- [COMPOSITE] Third-year students in Pune
SELECT * FROM Student WHERE year = 3 AND city = 'Pune';

-- [COMPOSITE] High-scoring enrollments in a specific semester
SELECT * FROM Enrollment WHERE marks > 85 AND semester = 'Spring 2024';

-- [COMPOSITE] Enrollments for a specific course with high marks
SELECT * FROM Enrollment WHERE course_id = 10 AND marks > 80;

-- [COMPOSITE] Low attendance in a specific course
SELECT * FROM Attendance WHERE course_id = 15 AND percentage < 40;

-- [COMPOSITE] Students in Physics from Delhi or Bangalore
SELECT * FROM Student WHERE department = 'Physics' AND (city = 'Delhi' OR city = 'Bangalore');


-- ============================================================
-- JOIN QUERIES (2-3 tables)
-- ============================================================

-- [JOIN] Students with their enrollment details
SELECT s.name, s.department, e.course_id, e.marks, e.semester FROM Student s JOIN Enrollment e ON s.student_id = e.student_id WHERE s.department = 'Computer Science';

-- [JOIN] Students with their course names
SELECT s.name, c.course_name, e.marks FROM Student s JOIN Enrollment e ON s.student_id = e.student_id JOIN Course c ON e.course_id = c.course_id WHERE s.city = 'Mumbai';

-- [JOIN] Students and their attendance with course info
SELECT s.name, c.course_name, a.percentage FROM Student s JOIN Attendance a ON s.student_id = a.student_id JOIN Course c ON a.course_id = c.course_id WHERE a.percentage < 50;

-- [JOIN] Enrollment details with course names for a semester
SELECT e.enrollment_id, s.name, c.course_name, e.marks FROM Enrollment e JOIN Student s ON e.student_id = s.student_id JOIN Course c ON e.course_id = c.course_id WHERE e.semester = 'Fall 2023';

-- [JOIN] Students enrolled in courses from a different department
SELECT s.name, s.department AS student_dept, c.course_name, c.department AS course_dept FROM Student s JOIN Enrollment e ON s.student_id = e.student_id JOIN Course c ON e.course_id = c.course_id WHERE s.department != c.department;


-- ============================================================
-- JOIN + GROUP BY (aggregation across joined tables)
-- ============================================================

-- [JOIN_GROUPBY] Average marks per department (via enrollment)
SELECT s.department, AVG(e.marks) AS avg_marks FROM Student s JOIN Enrollment e ON s.student_id = e.student_id GROUP BY s.department;

-- [JOIN_GROUPBY] Number of students enrolled per course
SELECT c.course_name, COUNT(DISTINCT e.student_id) AS student_count FROM Course c JOIN Enrollment e ON c.course_id = e.course_id GROUP BY c.course_name;

-- [JOIN_GROUPBY] Average attendance per department
SELECT s.department, AVG(a.percentage) AS avg_attendance FROM Student s JOIN Attendance a ON s.student_id = a.student_id GROUP BY s.department;

-- [JOIN_GROUPBY] Top 10 courses by average marks
SELECT c.course_name, AVG(e.marks) AS avg_marks FROM Course c JOIN Enrollment e ON c.course_id = e.course_id GROUP BY c.course_name ORDER BY avg_marks DESC LIMIT 10;

-- [JOIN_GROUPBY] Count of enrollments per student per semester
SELECT s.name, e.semester, COUNT(*) AS enrollment_count FROM Student s JOIN Enrollment e ON s.student_id = e.student_id GROUP BY s.student_id, s.name, e.semester;


-- ============================================================
-- ORDER BY (sorting queries)
-- ============================================================

-- [ORDERBY] Top 100 students by marks in a semester
SELECT s.name, e.marks FROM Student s JOIN Enrollment e ON s.student_id = e.student_id WHERE e.semester = 'Spring 2024' ORDER BY e.marks DESC LIMIT 100;

-- [ORDERBY] Students sorted by name in a department
SELECT * FROM Student WHERE department = 'Economics' ORDER BY name;

-- [ORDERBY] Attendance records sorted by percentage ascending
SELECT * FROM Attendance ORDER BY percentage ASC LIMIT 100;

-- [ORDERBY] Enrollments sorted by marks descending
SELECT * FROM Enrollment WHERE semester = 'Fall 2023' ORDER BY marks DESC LIMIT 50;


-- ============================================================
-- GROUP BY (standalone aggregation, no join)
-- ============================================================

-- [GROUPBY] Number of students per department
SELECT department, COUNT(*) AS student_count FROM Student GROUP BY department;

-- [GROUPBY] Number of students per city
SELECT city, COUNT(*) AS student_count FROM Student GROUP BY city;

-- [GROUPBY] Average marks per semester
SELECT semester, AVG(marks) AS avg_marks FROM Enrollment GROUP BY semester;

-- [GROUPBY] Number of courses per department
SELECT department, COUNT(*) AS course_count FROM Course GROUP BY department;

-- [GROUPBY] Average attendance per course
SELECT course_id, AVG(percentage) AS avg_pct FROM Attendance GROUP BY course_id;


-- ============================================================
-- LOW-FREQUENCY / ADMIN QUERIES (rare, deprioritize for indexing)
-- ============================================================

-- [LOW_FREQ] Full student table dump (admin export)
SELECT * FROM Student;

-- [LOW_FREQ] Count total enrollments across all semesters
SELECT COUNT(*) AS total_enrollments FROM Enrollment;

-- [LOW_FREQ] Find students not enrolled in any course
SELECT s.* FROM Student s LEFT JOIN Enrollment e ON s.student_id = e.student_id WHERE e.enrollment_id IS NULL;

-- [LOW_FREQ] Find courses with no enrollments
SELECT c.* FROM Course c LEFT JOIN Enrollment e ON c.course_id = e.course_id WHERE e.enrollment_id IS NULL;

-- [LOW_FREQ] Full cross-table report: student, course, marks, attendance
SELECT s.name, s.department, c.course_name, e.marks, a.percentage FROM Student s JOIN Enrollment e ON s.student_id = e.student_id JOIN Course c ON e.course_id = c.course_id LEFT JOIN Attendance a ON s.student_id = a.student_id AND c.course_id = a.course_id WHERE s.student_id <= 100;
