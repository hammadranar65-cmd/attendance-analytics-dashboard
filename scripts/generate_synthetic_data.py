"""
generate_synthetic_data.py — Builds a realistic synthetic attendance dataset.

Generates 5 courses, ~100 students, 1 semester (16 weeks, 3 sessions/week per
section), and writes everything to CSV files that match the database schema
in database/schema.sql. Run load_to_postgres.py afterward to load these CSVs
into your actual PostgreSQL database.

WHY THIS ISN'T JUST RANDOM NOISE:
Random present/absent flags would make every ML model in this project
pointless — there would be no real pattern to predict, detect, or forecast.
Instead this generator gives each student a "baseline reliability" and then
layers on deliberate, realistic patterns:

  - Some students decline gradually through the semester (the at-risk
    predictor should be able to catch this trend before the final percentage
    drops too low).
  - A few students have a specific day-of-week pattern (e.g. always missing
    Friday sessions) — this is what the anomaly/pattern detector should find.
  - Attendance dips after major breaks (e.g. mid-semester break) across
    almost everyone — this is what the trend forecaster should pick up on.
  - The three data sources (RFID, biometric, manual) have different noise
    characteristics: RFID rarely misses a present student but occasionally
    double-logs; biometric occasionally fails to read (false absent); manual
    entry has the most missing/incorrect records since it's done by hand.
"""

import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

random.seed(42)
np.random.seed(42)
fake = Faker()
Faker.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SEMESTER_LABEL = "Fall-2026"
SEMESTER_START = date(2026, 9, 1)   # a Tuesday
WEEKS = 16
N_STUDENTS = 100

COURSES = [
    ("COSC-301", "Database Systems", "rfid"),
    ("COSC-305", "Operating Systems", "biometric"),
    ("COSC-310", "Software Engineering", "manual"),
    ("COSC-315", "Computer Networks", "rfid"),
    ("COSC-320", "Artificial Intelligence", "biometric"),
]

# Each course meets twice a week on these day pairs (Mon/Wed, Tue/Thu, etc.)
DAY_PAIRS = [
    ("Monday", "Wednesday"),
    ("Tuesday", "Thursday"),
    ("Monday", "Thursday"),
    ("Tuesday", "Wednesday"),
    ("Wednesday", "Friday"),
]

WEEKDAY_MAP = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Friday": 4, "Saturday": 5, "Sunday": 6,
}

# Mid-semester break: attendance dips for everyone right after this
BREAK_WEEK = 8  # week index (0-based) treated as a break; sessions resume week 9 with a dip


def session_dates_for(day_names, start, weeks):
    """Generate actual calendar dates for a course meeting on given weekdays."""
    dates = []
    for week in range(weeks):
        if week == BREAK_WEEK:
            continue  # no sessions during break week
        for day_name in day_names:
            target_weekday = WEEKDAY_MAP[day_name]
            # find the date in this week matching target_weekday
            week_start = start + timedelta(weeks=week)
            delta = (target_weekday - week_start.weekday()) % 7
            session_date = week_start + timedelta(days=delta)
            dates.append((session_date, day_name, week))
    return sorted(dates)


def make_students(n):
    students = []
    for i in range(1, n + 1):
        students.append({
            "student_id": i,
            "roll_no": f"COSC-2311221-{i:03d}",
            "full_name": fake.name(),
            "program": "BSCS",
            "enrollment_year": 2023,
        })
    return pd.DataFrame(students)


def make_instructors(n=5):
    instructors = []
    for i in range(1, n + 1):
        instructors.append({
            "instructor_id": i,
            "full_name": f"Dr. {fake.last_name()}",
            "email": fake.email(),
        })
    return pd.DataFrame(instructors)


def make_courses_and_sections():
    courses, sections = [], []
    for idx, (code, title, method) in enumerate(COURSES, start=1):
        courses.append({"course_id": idx, "course_code": code, "course_title": title, "credit_hours": 3})
        sections.append({
            "section_id": idx,
            "course_id": idx,
            "instructor_id": idx,
            "section_label": "A",
            "semester": SEMESTER_LABEL,
            "attendance_method": method,
            "day_pair": DAY_PAIRS[idx - 1],
        })
    return pd.DataFrame(courses), pd.DataFrame(sections)


def make_enrollments(students_df, sections_df, enroll_fraction=0.85):
    """Each student enrolls in a random subset of sections (not all 5 courses)."""
    enrollments = []
    eid = 1
    for _, student in students_df.iterrows():
        n_courses = random.choice([3, 4, 5])  # most students take 3-5 of the 5 courses
        chosen_sections = random.sample(list(sections_df["section_id"]), n_courses)
        for sec_id in chosen_sections:
            enrollments.append({
                "enrollment_id": eid,
                "student_id": student["student_id"],
                "section_id": sec_id,
            })
            eid += 1
    return pd.DataFrame(enrollments)


def make_sessions(sections_df):
    sessions = []
    sid = 1
    for _, sec in sections_df.iterrows():
        for session_date, day_name, week in session_dates_for(sec["day_pair"], SEMESTER_START, WEEKS):
            sessions.append({
                "session_id": sid,
                "section_id": sec["section_id"],
                "session_date": session_date,
                "day_of_week": day_name,
                "week_index": week,
            })
            sid += 1
    return pd.DataFrame(sessions)


def assign_student_archetypes(students_df):
    """
    Assign each student a hidden 'archetype' that drives their attendance
    pattern. This is what the ML models are meant to discover from the data
    -- it's not stored in the database, just used internally to generate
    realistic behavior.
    """
    archetypes = {}
    n = len(students_df)

    # Roughly: 60% reliable, 15% declining (the at-risk group), 15% chronic
    # low attenders, 10% with a specific day-of-week quirk (anomaly target)
    ids = list(students_df["student_id"])
    random.shuffle(ids)

    n_declining = int(n * 0.15)
    n_chronic_low = int(n * 0.15)
    n_day_quirk = int(n * 0.10)

    declining_ids = set(ids[:n_declining])
    chronic_low_ids = set(ids[n_declining:n_declining + n_chronic_low])
    day_quirk_ids = set(ids[n_declining + n_chronic_low:n_declining + n_chronic_low + n_day_quirk])

    for sid in ids:
        if sid in declining_ids:
            archetypes[sid] = {"type": "declining", "base_rate": np.random.uniform(0.85, 0.95)}
        elif sid in chronic_low_ids:
            archetypes[sid] = {"type": "chronic_low", "base_rate": np.random.uniform(0.45, 0.65)}
        elif sid in day_quirk_ids:
            quirk_day = random.choice(["Friday", "Monday"])
            archetypes[sid] = {"type": "day_quirk", "base_rate": np.random.uniform(0.85, 0.95), "quirk_day": quirk_day}
        else:
            archetypes[sid] = {"type": "reliable", "base_rate": np.random.uniform(0.88, 0.98)}

    return archetypes


def simulate_attendance(sessions_df, enrollments_df, sections_df, archetypes):
    """
    Core simulation: for each (student, session) pair the student is enrolled
    in, decide present/absent/late based on their archetype, then apply
    source-specific noise (RFID/biometric/manual).
    """
    records = []
    rid = 1

    # group sessions by section for quick lookup
    sessions_by_section = {sid: df for sid, df in sessions_df.groupby("section_id")}
    method_by_section = dict(zip(sections_df["section_id"], sections_df["attendance_method"]))

    # enrollments grouped by student
    enroll_by_student = enrollments_df.groupby("student_id")["section_id"].apply(list)

    total_weeks = WEEKS

    for student_id, section_ids in enroll_by_student.items():
        arche = archetypes[student_id]

        for section_id in section_ids:
            method = method_by_section[section_id]
            sec_sessions = sessions_by_section.get(section_id)
            if sec_sessions is None:
                continue

            for _, sess in sec_sessions.iterrows():
                week = sess["week_index"]
                day = sess["day_of_week"]

                # --- true underlying probability of attending ---
                base = arche["base_rate"]

                if arche["type"] == "declining":
                    # linearly decays from base_rate toward ~0.4 by end of semester
                    progress = week / max(total_weeks - 1, 1)
                    prob = base - progress * (base - 0.40)
                elif arche["type"] == "day_quirk" and day == arche.get("quirk_day"):
                    prob = 0.15  # almost always absent on their quirk day
                else:
                    prob = base

                # mid-semester break dip: everyone's attendance dips slightly
                # for the 2 weeks right after the break
                if BREAK_WEEK < week <= BREAK_WEEK + 2:
                    prob *= 0.85

                prob = float(np.clip(prob, 0.03, 0.99))
                true_present = np.random.rand() < prob

                # --- apply source-specific noise on top of the true state ---
                status = "present" if true_present else "absent"

                if method == "rfid":
                    # RFID rarely misses a present student; small chance of
                    # logging "late" instead of "present"
                    if status == "present" and np.random.rand() < 0.07:
                        status = "late"
                elif method == "biometric":
                    # biometric occasionally fails to read a present student
                    # (false absent) due to a fingerprint misread
                    if status == "present" and np.random.rand() < 0.05:
                        status = "absent"
                    if status == "present" and np.random.rand() < 0.05:
                        status = "late"
                else:  # manual
                    # manual entry has the most noise: bigger chance of a
                    # present student wrongly marked late or even missed
                    if status == "present" and np.random.rand() < 0.10:
                        status = "late"
                    if status == "absent" and np.random.rand() < 0.03:
                        status = "present"  # instructor mis-marks by mistake

                records.append({
                    "record_id": rid,
                    "session_id": sess["session_id"],
                    "student_id": student_id,
                    "status": status,
                    "source": method,
                })
                rid += 1

    return pd.DataFrame(records)


def main():
    print("Generating students, instructors, courses, sections...")
    students_df = make_students(N_STUDENTS)
    instructors_df = make_instructors()
    courses_df, sections_df = make_courses_and_sections()

    print("Generating enrollments...")
    enrollments_df = make_enrollments(students_df, sections_df)

    print("Generating session calendar...")
    sessions_df = make_sessions(sections_df)

    print("Assigning hidden student archetypes (for realistic patterns)...")
    archetypes = assign_student_archetypes(students_df)

    print("Simulating attendance records (this is the big one)...")
    attendance_df = simulate_attendance(sessions_df, enrollments_df, sections_df, archetypes)

    # Drop helper columns not in the DB schema before export
    sections_export = sections_df.drop(columns=["day_pair"])
    sessions_export = sessions_df.drop(columns=["week_index"])

    print("Writing CSV files...")
    students_df.to_csv(os.path.join(OUTPUT_DIR, "students.csv"), index=False)
    instructors_df.to_csv(os.path.join(OUTPUT_DIR, "instructors.csv"), index=False)
    courses_df.to_csv(os.path.join(OUTPUT_DIR, "courses.csv"), index=False)
    sections_export.to_csv(os.path.join(OUTPUT_DIR, "sections.csv"), index=False)
    enrollments_df.to_csv(os.path.join(OUTPUT_DIR, "enrollments.csv"), index=False)
    sessions_export.to_csv(os.path.join(OUTPUT_DIR, "sessions.csv"), index=False)
    attendance_df.to_csv(os.path.join(OUTPUT_DIR, "attendance_records.csv"), index=False)

    # Also save the "ground truth" archetypes for later validation of the
    # ML models (NOT used as a feature — only to check if models found the
    # patterns we deliberately planted).
    archetype_rows = [{"student_id": sid, **info} for sid, info in archetypes.items()]
    pd.DataFrame(archetype_rows).to_csv(
        os.path.join(OUTPUT_DIR, "_ground_truth_archetypes.csv"), index=False
    )

    print(f"\nDone. {len(students_df)} students, {len(courses_df)} courses, "
          f"{len(sessions_df)} sessions, {len(attendance_df)} attendance records.")
    print(f"Files written to: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
