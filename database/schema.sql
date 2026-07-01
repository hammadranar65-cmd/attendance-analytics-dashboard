-- ============================================================
-- Attendance Analytics Dashboard — Database Schema
-- PostgreSQL
-- ============================================================
-- Run this first to create all tables. Safe to re-run: drops
-- existing tables first (DEV ONLY — remove the DROP lines once
-- you have real data you care about keeping).
-- ============================================================

DROP TABLE IF EXISTS attendance_records CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS enrollments CASCADE;
DROP TABLE IF EXISTS sections CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS instructors CASCADE;
DROP TABLE IF EXISTS model_outputs CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ----------------------------------------------------------------
-- Core academic entities
-- ----------------------------------------------------------------

CREATE TABLE students (
    student_id      SERIAL PRIMARY KEY,
    roll_no          VARCHAR(30) UNIQUE NOT NULL,
    full_name        VARCHAR(120) NOT NULL,
    program          VARCHAR(80),
    enrollment_year  INT,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE instructors (
    instructor_id    SERIAL PRIMARY KEY,
    full_name        VARCHAR(120) NOT NULL,
    email            VARCHAR(150) UNIQUE,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE courses (
    course_id        SERIAL PRIMARY KEY,
    course_code      VARCHAR(20) UNIQUE NOT NULL,   -- e.g. 'COSC-301'
    course_title     VARCHAR(150) NOT NULL,
    credit_hours     INT DEFAULT 3
);

CREATE TABLE sections (
    section_id       SERIAL PRIMARY KEY,
    course_id        INT NOT NULL REFERENCES courses(course_id),
    instructor_id    INT REFERENCES instructors(instructor_id),
    section_label    VARCHAR(10) NOT NULL,           -- e.g. 'A', 'B'
    semester          VARCHAR(20) NOT NULL,           -- e.g. 'Fall-2026'
    -- which attendance method this section primarily uses;
    -- still allows mixed records, this is just the default/expected one
    attendance_method VARCHAR(20) DEFAULT 'manual'    -- 'rfid' | 'biometric' | 'manual'
        CHECK (attendance_method IN ('rfid', 'biometric', 'manual')),
    UNIQUE (course_id, section_label, semester)
);

CREATE TABLE enrollments (
    enrollment_id    SERIAL PRIMARY KEY,
    student_id       INT NOT NULL REFERENCES students(student_id),
    section_id       INT NOT NULL REFERENCES sections(section_id),
    enrolled_on      DATE DEFAULT CURRENT_DATE,
    UNIQUE (student_id, section_id)
);

-- One row per class meeting (e.g. "COSC-301 Section A, Monday Sep 1, 9:00am")
CREATE TABLE sessions (
    session_id       SERIAL PRIMARY KEY,
    section_id       INT NOT NULL REFERENCES sections(section_id),
    session_date     DATE NOT NULL,
    day_of_week      VARCHAR(10),                     -- denormalized for fast querying
    UNIQUE (section_id, session_date)
);

-- One row per student per session: the actual attendance fact table
CREATE TABLE attendance_records (
    record_id        SERIAL PRIMARY KEY,
    session_id       INT NOT NULL REFERENCES sessions(session_id),
    student_id       INT NOT NULL REFERENCES students(student_id),
    status           VARCHAR(10) NOT NULL DEFAULT 'absent'
        CHECK (status IN ('present', 'absent', 'late')),
    source           VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (source IN ('rfid', 'biometric', 'manual')),
    recorded_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (session_id, student_id)
);

-- ----------------------------------------------------------------
-- AI/ML output caching (so the dashboard doesn't recompute on every load)
-- ----------------------------------------------------------------

CREATE TABLE model_outputs (
    output_id        SERIAL PRIMARY KEY,
    model_name       VARCHAR(50) NOT NULL,   -- 'at_risk' | 'anomaly' | 'forecast' | 'summary'
    entity_type      VARCHAR(20) NOT NULL,   -- 'student' | 'section' | 'course'
    entity_id        INT NOT NULL,
    result_json      JSONB NOT NULL,
    computed_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_model_outputs_lookup ON model_outputs (model_name, entity_type, entity_id);

-- ----------------------------------------------------------------
-- App users (instructors / dept heads / admins logging into the dashboard)
-- ----------------------------------------------------------------

CREATE TABLE users (
    user_id          SERIAL PRIMARY KEY,
    full_name        VARCHAR(120) NOT NULL,
    email            VARCHAR(150) UNIQUE NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    role             VARCHAR(20) NOT NULL DEFAULT 'instructor'
        CHECK (role IN ('instructor', 'department_head', 'admin')),
    instructor_id    INT REFERENCES instructors(instructor_id),  -- null for dept_head/admin
    created_at       TIMESTAMP DEFAULT NOW()
);

-- ----------------------------------------------------------------
-- Helpful indexes for the queries the dashboard will run constantly
-- ----------------------------------------------------------------

CREATE INDEX idx_attendance_student ON attendance_records (student_id);
CREATE INDEX idx_attendance_session ON attendance_records (session_id);
CREATE INDEX idx_sessions_section_date ON sessions (section_id, session_date);
CREATE INDEX idx_enrollments_student ON enrollments (student_id);
CREATE INDEX idx_enrollments_section ON enrollments (section_id);
