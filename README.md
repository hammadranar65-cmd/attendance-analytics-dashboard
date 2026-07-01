# Attendance Analytics Dashboard — Stage 1: Database & Synthetic Data

This is the foundation stage of the project: the PostgreSQL schema and a
realistic synthetic dataset to build and test everything else against.

## What's in this stage

```
attendance-dashboard/
├── database/
│   └── schema.sql                  <- run this first to create all tables
├── scripts/
│   ├── generate_synthetic_data.py  <- creates realistic fake attendance data
│   └── load_to_postgres.py         <- loads the generated CSVs into PostgreSQL
├── data/                           <- generated CSV files land here
└── requirements.txt
```

## Why the synthetic data isn't just random

If attendance were purely random, none of the 4 AI/ML modules in the
proposal (at-risk prediction, anomaly detection, trend forecasting, AI
summaries) would have anything real to learn — there'd be no signal, just
noise. So this generator deliberately plants realistic patterns:

- **60% reliable students** — consistently high attendance (88-98%)
- **15% declining students** — start fine, gradually drop to ~35-40% by
  the end of the semester (this is exactly what the at-risk predictor
  should catch *before* it gets that low)
- **15% chronic low attenders** — consistently around 45-65% all semester
- **10% "day quirk" students** — almost always absent on one specific
  weekday (e.g. always misses Monday) — this is the pattern the
  anomaly/pattern detector should surface
- **A mid-semester break dip** — everyone's attendance dips slightly for
  2 weeks right after a semester break, which the trend forecaster should
  pick up on
- **Source-specific noise** — RFID, biometric, and manual entry each have
  different, realistic error patterns (e.g. biometric occasionally
  fails to read a present student; manual entry has the most mistakes)

This was verified after generation: the declining group's attendance
actually drops from ~89% to ~35% across the semester, day-quirk students
show a clear single-day dip, and reliable vs. chronic-low students show a
clean separation (89.5% vs 51.8%) — confirming the patterns are real and
learnable, not accidental.

## Setup (Windows + VS Code, same flow as the Sara project)

1. **Install PostgreSQL** if you don't have it:
   https://www.postgresql.org/download/windows/
   During install, remember the password you set for the `postgres` user.

2. **Create the database.** Open the SQL Shell (psql) that comes with
   PostgreSQL, or use pgAdmin, and run:
   ```sql
   CREATE DATABASE attendance_db;
   ```

3. **Apply the schema.** From a terminal:
   ```
   psql -U postgres -d attendance_db -f database/schema.sql
   ```
   (It will ask for your postgres password.)

4. **Set up a Python virtual environment** (in this project folder):
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. **Generate the synthetic dataset:**
   ```
   python scripts/generate_synthetic_data.py
   ```
   This writes CSV files into the `data/` folder. You can open
   `data/attendance_records.csv` etc. in Excel to eyeball them.

6. **Load the data into PostgreSQL:**
   ```
   set PGPASSWORD=your_postgres_password
   python scripts/load_to_postgres.py
   ```
   (On PowerShell, use `$env:PGPASSWORD="your_postgres_password"` instead
   of `set`.)

7. **Verify it worked.** In psql or pgAdmin:
   ```sql
   SELECT COUNT(*) FROM attendance_records;
   -- should return 12000 (5 courses x ~100 students x ~24 sessions, roughly)

   SELECT s.full_name, COUNT(*) as sessions,
          SUM(CASE WHEN a.status != 'absent' THEN 1 ELSE 0 END) as present_count
   FROM attendance_records a
   JOIN students s ON s.student_id = a.student_id
   GROUP BY s.full_name
   ORDER BY present_count ASC
   LIMIT 10;
   -- shows your 10 worst-attendance students
   ```

## A note on `_ground_truth_archetypes.csv`

This file (also written to `data/`) records which "hidden pattern" each
student was assigned (reliable / declining / chronic_low / day_quirk) —
this is **not** loaded into the database and the dashboard/models should
never see it directly. It exists purely so we can later check whether the
ML models actually rediscover these patterns from the attendance data
alone, which is how we'll validate the models are working correctly
before trusting them on l real data.

## What's next

With the database populated, the next stages are:
1. A data-access layer (Python functions / API endpoints to query attendance)
2. The 4 AI/ML models, trained against this data and validated against
   `_ground_truth_archetypes.csv`
3. The dashboard frontend

Ask Claude to continue with whichever stage you want to tackle next.
