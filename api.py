"""
api.py – FastAPI backend that serves attendance data to the React frontend
Run with: uvicorn api:app --reload --port 8000
"""

import os
import json
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Attendance Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "model_outputs")


def load_merged():
    attendance = pd.read_csv(os.path.join(DATA_DIR, "attendance_records.csv"))
    sessions = pd.read_csv(os.path.join(DATA_DIR, "sessions.csv"), parse_dates=["session_date"])
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    sections = pd.read_csv(os.path.join(DATA_DIR, "sections.csv"))
    courses = pd.read_csv(os.path.join(DATA_DIR, "courses.csv"))

    min_date = sessions["session_date"].min()
    sessions["week_index"] = ((sessions["session_date"] - min_date).dt.days // 7)

    att = attendance.merge(
        sessions[["session_id", "week_index", "day_of_week", "section_id"]],
        on="session_id"
    )
    att["present"] = (att["status"] != "absent").astype(int)
    att = att.merge(students[["student_id", "full_name", "roll_no"]], on="student_id")
    att = att.merge(sections[["section_id", "course_id", "section_label"]], on="section_id")
    att = att.merge(courses[["course_id", "course_title"]], on="course_id")
    return att


@app.get("/api/overview")
def get_overview():
    att = load_merged()
    at_risk = pd.read_csv(os.path.join(OUTPUT_DIR, "at_risk_predictions.csv"))
    anomalies = pd.read_csv(os.path.join(OUTPUT_DIR, "anomaly_detections.csv"))

    return {
        "total_students": int(att["student_id"].nunique()),
        "overall_rate": round(float(att["present"].mean()), 4),
        "at_risk_count": int(len(at_risk[at_risk["predicted_at_risk"] == 1])),
        "anomaly_count": int(len(anomalies[anomalies["is_anomaly"] == 1])),
    }


@app.get("/api/weekly-trends")
def get_weekly_trends():
    att = load_merged()
    weekly = att.groupby(["course_title", "week_index"])["present"].mean().reset_index()
    weekly["present"] = weekly["present"].round(4)
    return weekly.to_dict(orient="records")


@app.get("/api/at-risk")
def get_at_risk():
    df = pd.read_csv(os.path.join(OUTPUT_DIR, "at_risk_predictions.csv"))
    flagged = df[df["predicted_at_risk"] == 1].sort_values("risk_probability", ascending=False)
    flagged = flagged[["full_name", "roll_no", "overall_rate", "projected_final", "risk_probability"]]
    flagged = flagged.round(4)
    return flagged.to_dict(orient="records")


@app.get("/api/anomalies")
def get_anomalies():
    df = pd.read_csv(os.path.join(OUTPUT_DIR, "anomaly_detections.csv"))
    flagged = df[df["is_anomaly"] == 1]
    flagged = flagged[["full_name", "roll_no", "overall_rate", "anomaly_type", "max_streak"]]
    flagged = flagged.round(4)
    return flagged.to_dict(orient="records")


@app.get("/api/forecast")
def get_forecast():
    df = pd.read_csv(os.path.join(OUTPUT_DIR, "forecast_summary.csv"))
    return df.round(4).to_dict(orient="records")


@app.get("/api/summaries")
def get_summaries():
    with open(os.path.join(OUTPUT_DIR, "ai_summaries.json")) as f:
        return json.load(f)


@app.get("/api/students")
def get_students():
    att = load_merged()
    students = att.groupby(["student_id", "full_name", "roll_no"])["present"].mean().reset_index()
    students.columns = ["student_id", "full_name", "roll_no", "overall_rate"]
    students = students.sort_values("full_name")
    return students.round(4).to_dict(orient="records")


@app.get("/api/student/{student_id}")
def get_student_detail(student_id: int):
    att = load_merged()
    s = att[att["student_id"] == student_id]
    if len(s) == 0:
        return {"error": "Student not found"}

    weekly = s.groupby("week_index")["present"].mean().reset_index()
    weekly.columns = ["week", "rate"]

    by_course = s.groupby("course_title")["present"].mean().reset_index()
    by_course.columns = ["course", "rate"]

    return {
        "student_id": student_id,
        "full_name": s["full_name"].iloc[0],
        "roll_no": s["roll_no"].iloc[0],
        "overall_rate": round(float(s["present"].mean()), 4),
        "weekly": weekly.round(4).to_dict(orient="records"),
        "by_course": by_course.round(4).to_dict(orient="records"),
    }


@app.get("/api/heatmap")
def get_heatmap():
    att = load_merged()
    pivot = att.groupby(["day_of_week", "week_index"])["present"].mean().reset_index()
    pivot["present"] = pivot["present"].round(4)
    return pivot.to_dict(orient="records")