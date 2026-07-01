"""
model_forecast.py — Attendance Trend Forecaster
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "model_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TOTAL_WEEKS = 16
OBSERVATION_WEEK = 8


def load_data():
    print("Loading data...")
    attendance = pd.read_csv(os.path.join(DATA_DIR, "attendance_records.csv"))
    sessions = pd.read_csv(os.path.join(DATA_DIR, "sessions.csv"), parse_dates=["session_date"])
    sections = pd.read_csv(os.path.join(DATA_DIR, "sections.csv"))
    courses = pd.read_csv(os.path.join(DATA_DIR, "courses.csv"))
    return attendance, sessions, sections, courses


def add_week_index(sessions_df):
    sessions_df = sessions_df.copy()
    min_date = sessions_df["session_date"].min()
    sessions_df["week_index"] = ((sessions_df["session_date"] - min_date).dt.days // 7)
    return sessions_df


def forecast_section(section_id, att_section, observation_week, total_weeks):
    """Forecast attendance trend for one section using linear regression."""
    observed = att_section[att_section["week_index"] < observation_week]
    weekly = observed.groupby("week_index")["present"].mean().reset_index()
    weekly.columns = ["week", "rate"]

    if len(weekly) < 3:
        return None

    X = weekly["week"].values.reshape(-1, 1)
    y = weekly["rate"].values

    model = LinearRegression()
    model.fit(X, y)

    # Forecast remaining weeks
    future_weeks = list(range(observation_week, total_weeks))
    future_X = np.array(future_weeks).reshape(-1, 1)
    forecast = model.predict(future_X)
    forecast = np.clip(forecast, 0, 1)

    # Actual rates (for comparison)
    actual = att_section.groupby("week_index")["present"].mean().reset_index()
    actual.columns = ["week", "rate"]

    return {
        "section_id": section_id,
        "slope": model.coef_[0],
        "observed_weeks": weekly,
        "forecast_weeks": pd.DataFrame({"week": future_weeks, "rate": forecast}),
        "actual_weeks": actual,
    }


def plot_forecast(result, course_title, section_label, output_dir):
    """Plot observed vs forecasted attendance for one section."""
    plt.figure(figsize=(10, 5))

    obs = result["observed_weeks"]
    fut = result["forecast_weeks"]
    act = result["actual_weeks"]

    # Actual full trend (light grey)
    plt.plot(act["week"], act["rate"], color="lightgrey",
             linewidth=1.5, label="Actual (full semester)", zorder=1)

    # Observed portion used for training
    plt.plot(obs["week"], obs["rate"], color="steelblue",
             linewidth=2.5, marker="o", markersize=5,
             label=f"Observed (weeks 0-{result['observed_weeks']['week'].max()})", zorder=2)

    # Forecast
    plt.plot(fut["week"], fut["rate"], color="crimson",
             linewidth=2, linestyle="--", marker="x", markersize=5,
             label="Forecast (remaining weeks)", zorder=3)

    # Vertical line at observation cutoff
    plt.axvline(x=result["observed_weeks"]["week"].max(),
                color="orange", linestyle=":", linewidth=1.5, label="Observation cutoff")

    # 75% threshold line
    plt.axhline(y=0.75, color="red", linestyle="--",
                linewidth=1, alpha=0.5, label="75% threshold")

    plt.ylim(0, 1.05)
    plt.xlabel("Week")
    plt.ylabel("Attendance Rate")
    slope_dir = "↑ Improving" if result["slope"] > 0 else "↓ Declining"
    plt.title(f"{course_title} — Section {section_label}\n"
              f"Trend: {slope_dir} ({result['slope']:+.3f}/week)")
    plt.legend(fontsize=8)
    plt.tight_layout()

    safe_title = course_title.replace(" ", "_").replace("/", "_")
    path = os.path.join(output_dir, f"forecast_{safe_title}_{section_label}.png")
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def main():
    print("=" * 55)
    print("ATTENDANCE TREND FORECASTER")
    print(f"Observation: Week {OBSERVATION_WEEK} of {TOTAL_WEEKS}")
    print("=" * 55)

    attendance, sessions, sections, courses = load_data()
    sessions = add_week_index(sessions)

    att = attendance.merge(
        sessions[["session_id", "week_index", "section_id"]], on="session_id"
    )
    att["present"] = (att["status"] != "absent").astype(int)

    course_map = dict(zip(courses["course_id"], courses["course_title"]))
    section_course_map = dict(zip(sections["section_id"], sections["course_id"]))
    section_label_map = dict(zip(sections["section_id"], sections["section_label"]))

    summary_rows = []
    print("\nForecasting per section...\n")

    for section_id in sections["section_id"].unique():
        att_section = att[att["section_id"] == section_id]
        if len(att_section) == 0:
            continue

        result = forecast_section(
            section_id, att_section, OBSERVATION_WEEK, TOTAL_WEEKS
        )
        if result is None:
            continue

        course_id = section_course_map[section_id]
        course_title = course_map.get(course_id, f"Course {course_id}")
        section_label = section_label_map.get(section_id, "A")

        # Current observed rate
        current_rate = result["observed_weeks"]["rate"].iloc[-1]
        # Projected final rate
        projected_final = result["forecast_weeks"]["rate"].iloc[-1]
        trend = "Improving" if result["slope"] > 0.005 else \
                "Declining" if result["slope"] < -0.005 else "Stable"

        print(f"{course_title} (Section {section_label}):")
        print(f"  Current rate : {current_rate:.1%}")
        print(f"  Projected end: {projected_final:.1%}")
        print(f"  Trend        : {trend} (slope={result['slope']:+.4f}/week)")
        print()

        # Plot
        path = plot_forecast(result, course_title, section_label, OUTPUT_DIR)
        print(f"  Chart saved: {path}\n")

        summary_rows.append({
            "section_id": section_id,
            "course_title": course_title,
            "section_label": section_label,
            "current_rate": round(current_rate, 4),
            "projected_final": round(projected_final, 4),
            "slope": round(result["slope"], 5),
            "trend": trend,
        })

    # Save summary
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(
        os.path.join(OUTPUT_DIR, "forecast_summary.csv"), index=False
    )

    print("=== FORECAST SUMMARY ===")
    print(f"{'Course':<35} {'Current':>9} {'Projected':>10} {'Trend'}")
    print("-" * 65)
    for _, row in summary_df.iterrows():
        print(f"{row['course_title']:<35} "
              f"{row['current_rate']:.1%}    "
              f"{row['projected_final']:.1%}     "
              f"{row['trend']}")

    print(f"\nAll outputs saved to: data/model_outputs/")
    print("\nDone! Model 3 complete.")


if __name__ == "__main__":
    main()