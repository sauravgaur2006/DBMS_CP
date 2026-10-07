-- ============================================================
-- Automatic Index Recommendation System — Rollback Script
-- Drops all recommended secondary indexes to return to baseline
-- ============================================================
USE index_recommender;

DROP INDEX `idx_student_student_id` ON `Student`;
DROP INDEX `idx_course_course_id` ON `Course`;
DROP INDEX `idx_student_department` ON `Student`;
DROP INDEX `idx_student_city` ON `Student`;
DROP INDEX `idx_attendance_student_id` ON `Attendance`;
DROP INDEX `idx_enrollment_semester_marks` ON `Enrollment`;
DROP INDEX `idx_student_course_id` ON `Student`;
DROP INDEX `idx_attendance_course_id` ON `Attendance`;
