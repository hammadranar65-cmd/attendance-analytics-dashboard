"""
model_summary.py — AI-Generated Plain Language Insight Summaries

Reads outputs from Models 1, 2, and 3 and generates
clear, human-readable summaries for each course — the
kind an instructor can read in 30 seconds.
"""

import os
import json
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "model_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

AT_RISK_THRESHOLD = 0.75


def load_model_outputs():
    at_risk = pd.read_csv(os.path.join(OUTPUT_DIR, "at_risk_predictions.csv"))
    anomalies = pd.read_csv(os.path.join(OUTPUT_DIR, "anomaly_detections.csv"))
    forecast = pd.read_csv(os.path.join(OUTPUT_DIR, "forecast_summary.csv"))
    attendance = pd.read_csv(os.path.join(DATA_DIR, "attendance_records.csv"))
    sessions = pd.read_csv(os.path.join(DATA_DIR, "sessions.csv"), parse_dates=["session_date"])
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    sections = pd.read_csv(os.path.join(DATA_DIR, "sections.csv"))
    courses = pd.read_csv(os.path.join(DATA_DIR, "courses.csv"))
    return at_risk, anomalies, forecast, attendance, sessions, students, sections, courses


def generate_course_summary(course_title, forecast_row, at_risk_df,
                             anomaly_df, students_df):
    """Generate a plain-language paragraph summary for one course."""
    lines = []

    # --- Trend summary ---
    trend = forecast_row["trend"]
    current = forecast_row["current_rate"]
    projected = forecast_row["projected_final"]

    if trend == "Declining":
        lines.append(
            f"Attendance in {course_title} is currently at {current:.1%} "
            f"and is declining — projected to reach {projected:.1%} by end of semester. "
            f"This course needs immediate attention."
        )
    elif trend == "Improving":
        lines.append(
            f"Attendance in {course_title} is at {current:.1%} "
            f"and trending upward, projected to reach {projected:.1%} by semester end. "
            f"Things are looking good here."
        )
    else:
        lines.append(
            f"Attendance in {course_title} is stable at around {current:.1%}, "
            f"projected to stay near {projected:.1%} by semester end."
        )

    # --- At-risk students ---
    at_risk_students = at_risk_df[at_risk_df["predicted_at_risk"] == 1]
    n_at_risk = len(at_risk_students)

    if n_at_risk > 0:
        names = ", ".join(at_risk_students["full_name"].head(3).tolist())
        if n_at_risk > 3:
            names += f" and {n_at_risk - 3} others"
        lines.append(
            f"{n_at_risk} student(s) are at risk of falling below the 75% "
            f"attendance threshold: {names}."
        )
    else:
        lines.append("No students are currently at risk of breaching the attendance threshold.")

    # --- Anomalies ---
    anomalous = anomaly_df[anomaly_df["is_anomaly"] == 1]
    n_anomalies = len(anomalous)

    if n_anomalies > 0:
        anomaly_types = anomalous["anomaly_type"].value_counts()
        top_type = anomaly_types.index[0]
        lines.append(
            f"{n_anomalies} student(s) show unusual absence patterns "
            f"(most common: {top_type}). These may need a follow-up."
        )

    # --- Day quirk check ---
    day_quirks = anomalous[anomalous["anomaly_type"].str.startswith("day_quirk", na=False)]
    if len(day_quirks) > 0:
        lines.append(
            f"Note: {len(day_quirks)} student(s) appear to consistently "
            f"miss a specific day of the week — this pattern is worth investigating."
        )

    return " ".join(lines)


def generate_overall_summary(forecast_df, at_risk_df, anomaly_df):
    """Generate an overall department-level summary."""
    n_at_risk = len(at_risk_df[at_risk_df["predicted_at_risk"] == 1])
    n_anomaly = len(anomaly_df[anomaly_df["is_anomaly"] == 1])
    declining = forecast_df[forecast_df["trend"] == "Declining"]["course_title"].tolist()
    improving = forecast_df[forecast_df["trend"] == "Improving"]["course_title"].tolist()
    avg_rate = forecast_df["current_rate"].mean()

    lines = [
        f"DEPARTMENT OVERVIEW — Fall 2026",
        f"",
        f"Overall average attendance across all courses: {avg_rate:.1%}.",
    ]

    if declining:
        lines.append(f"Courses with declining attendance: {', '.join(declining)}.")
    if improving:
        lines.append(f"Courses with improving attendance: {', '.join(improving)}.")

    lines.append(
        f"Across all courses, {n_at_risk} student(s) are flagged as at-risk "
        f"of falling below the 75% threshold."
    )
    lines.append(
        f"{n_anomaly} student(s) show unusual or anomalous attendance patterns "
        f"that may warrant instructor follow-up."
    )

    return "\n".join(lines)


def main():
    print("=" * 55)
    print("AI SUMMARY GENERATOR")
    print("=" * 55)

    print("\nLoading model outputs...")
    (at_risk, anomalies, forecast,
     attendance, sessions, students, sections, courses) = load_model_outputs()

    all_summaries = {}

    # --- Overall department summary ---
    print("\nGenerating department overview...")
    overall = generate_overall_summary(forecast, at_risk, anomalies)
    all_summaries["DEPARTMENT_OVERVIEW"] = overall
    print("\n" + "=" * 55)
    print(overall)
    print("=" * 55)

    # --- Per-course summaries ---
    print("\nGenerating per-course summaries...\n")
    for _, forecast_row in forecast.iterrows():
        course_title = forecast_row["course_title"]

        summary = generate_course_summary(
            course_title=course_title,
            forecast_row=forecast_row,
            at_risk_df=at_risk,
            anomaly_df=anomalies,
            students_df=students,
        )

        all_summaries[course_title] = summary

        print(f"--- {course_title} ---")
        print(summary)
        print()

    # --- Save all summaries ---
    output_path = os.path.join(OUTPUT_DIR, "ai_summaries.json")
    with open(output_path, "w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"All summaries saved to: {output_path}")

    # Also save as readable text file
    txt_path = os.path.join(OUTPUT_DIR, "ai_summaries.txt")
    with open(txt_path, "w") as f:
        for title, summary in all_summaries.items():
            f.write(f"\n{'='*55}\n")
            f.write(f"{title}\n")
            f.write(f"{'='*55}\n")
            f.write(summary + "\n")
    print(f"Text version saved to: {txt_path}")

    print("\nDone! Model 4 complete.")
    print("\nAll 4 models are now complete:")
    print("  Model 1: At-Risk Prediction     → at_risk_predictions.csv")
    print("  Model 2: Anomaly Detection       → anomaly_detections.csv")
    print("  Model 3: Trend Forecasting       → forecast_summary.csv")
    print("  Model 4: AI Summaries            → ai_summaries.txt")


if __name__ == "__main__":
    main()