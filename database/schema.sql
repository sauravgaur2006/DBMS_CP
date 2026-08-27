-- ============================================================
-- Automatic Index Recommendation — Database Schema
-- Run as: mysql -u root -p < database/schema.sql
-- ============================================================

-- Drop and recreate the database from scratch
DROP DATABASE IF EXISTS index_recommender;
CREATE DATABASE index_recommender CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE index_recommender;

-- ============================================================
-- Table: Student
-- ============================================================
CREATE TABLE Student (
    student_id   INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(100)  NOT NULL,
    department   VARCHAR(50)   NOT NULL,
    year         INT           NOT NULL,
    city         VARCHAR(50)   NOT NULL
) ENGINE=InnoDB;

-- ============================================================
-- Table: Course
-- ============================================================
CREATE TABLE Course (
    course_id    INT AUTO_INCREMENT PRIMARY KEY,
    course_name  VARCHAR(100)  NOT NULL,
    department   VARCHAR(50)   NOT NULL
) ENGINE=InnoDB;

-- ============================================================
-- Table: Enrollment
-- ============================================================
CREATE TABLE Enrollment (
    enrollment_id  INT AUTO_INCREMENT PRIMARY KEY,
    student_id     INT            NOT NULL,
    course_id      INT            NOT NULL,
    marks          DECIMAL(5,2),
    semester       VARCHAR(20)    NOT NULL,
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (course_id)  REFERENCES Course(course_id)
) ENGINE=InnoDB;

-- ============================================================
-- Table: Attendance
-- ============================================================
CREATE TABLE Attendance (
    attendance_id  INT AUTO_INCREMENT PRIMARY KEY,
    student_id     INT            NOT NULL,
    course_id      INT            NOT NULL,
    percentage     DECIMAL(5,2)   NOT NULL,
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (course_id)  REFERENCES Course(course_id)
) ENGINE=InnoDB;
