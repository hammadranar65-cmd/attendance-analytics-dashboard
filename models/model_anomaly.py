"""
model_anomaly.py — Attendance Pattern & Anomaly Detector
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "model_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_data():
    print("Loading data...")
    attendance = pd.read_csv(os.path.join(DATA_DIR, "attendance_records.csv"))
    sessions = pd.read_csv(os.path.join(DATA_DIR, "sessions.csv"), parse_dates=["session_date"])
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    ground_truth = pd.read_csv(os.path.join(DATA_DIR, "_ground_truth_archetypes.csv"))
    return attendance, sessions, students, ground_truth


def add_week_index(sessions_df):
    sessions_df = sessions_df.copy()
    min_date = sessions_df["session_date"].min()
    sessions_df["week_index"] = ((sessions_df["session_date"] - min_date).dt.days // 7)
    return sessions_df


def engineer_anomaly_features(attendance, sessions):
    sessions = add_week_index(sessions)
    att = attendance.merge(
        sessions[["session_id", "week_index", "day_of_week"]], on="session_id"
    )
    att["present"] = (att["status"] != "absent").astype(int)

    features_list = []

    for student_id in att["student_id"].unique():
        s = att[att["student_id"] == student_id]

        # Overall rate
        overall_rate = s["present"].mean()

        # Attendance rate per day of week
        day_rates = s.groupby("day_of_week")["present"].mean()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_features = {f"rate_{d.lower()}": day_rates.get(d, overall_rate) for d in days}

        # Std deviation across days — high std = suspicious day pattern
        day_std = np.std(list(day_features.values()))

        # Min day rate — if one day is very low, that's anomalous
        min_day_rate = min(day_features.values())

        # Week-by-week variance — high variance = erratic attendance
        weekly_rates = s.groupby("week_index")["present"].mean()
        weekly_variance = weekly_rates.var() if len(weekly_rates) > 1 else 0.0
        weekly_std = weekly_rates.std() if len(weekly_rates) > 1 else 0.0

        # Sudden drop detection — biggest single-week decline
        if len(weekly_rates) > 2:
            diffs = weekly_rates.diff().dropna()
            biggest_drop = diffs.min()  # most negative = biggest drop
        else:
            biggest_drop = 0.0

        # Mid-semester attendance vs early (did they disappear mid-semester?)
        early_rate = s[s["week_index"] < 5]["present"].mean()
        mid_rate = s[(s["week_index"] >= 5) & (s["week_index"] < 10)]["present"].mean()
        late_rate = s[s["week_index"] >= 10]["present"].mean()

        mid_drop = (mid_rate - early_rate) if not np.isnan(mid_rate) else 0.0
        late_drop = (late_rate - early_rate) if not np.isnan(late_rate) else 0.0

        # Consecutive absence streaks
        sorted_s = s.sort_values("week_index")
        max_streak = 0
        streak = 0
        for _, row in sorted_s.iterrows():
            if row["present"] == 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        row_data = {
            "student_id": student_id,
            "overall_rate": overall_rate,
            "day_std": day_std,
            "min_day_rate": min_day_rate,
            "weekly_variance": weekly_variance,
            "weekly_std": weekly_std,
            "biggest_drop": biggest_drop,
            "early_rate": early_rate if not np.isnan(early_rate) else overall_rate,
            "mid_drop": mid_drop,
            "late_drop": late_drop,
            "max_streak": max_streak,
            **day_features,
        }
        features_list.append(row_data)

    return pd.DataFrame(features_list)


FEATURE_COLS = [
    "overall_rate", "day_std", "min_day_rate",
    "weekly_variance", "weekly_std", "biggest_drop",
    "early_rate", "mid_drop", "late_drop", "max_streak",
    "rate_monday", "rate_tuesday", "rate_wednesday",
    "rate_thursday", "rate_friday",
]


def detect_anomalies(features_df):
    X = features_df[FEATURE_COLS].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Isolation Forest: flags unusual attendance patterns automatically
    # contamination = expected fraction of anomalies in the data
    iso = IsolationForest(
        n_estimators=200,
        contamination=0.20,  # expect ~20% of students to have notable patterns
        random_state=42,
    )
    features_df = features_df.copy()
    features_df["anomaly_score"] = iso.fit_predict(X_scaled)
    features_df["anomaly_raw_score"] = iso.score_samples(X_scaled)

    # -1 = anomaly, 1 = normal (IsolationForest convention)
    features_df["is_anomaly"] = (features_df["anomaly_score"] == -1).astype(int)

    return features_df, iso, scaler


def classify_anomaly_type(row):
    """Give each detected anomaly a human-readable label."""
    if row["is_anomaly"] == 0:
        return "normal"

    # Day-of-week quirk: one specific day is much lower than others
    days = ["rate_monday", "rate_tuesday", "rate_wednesday", "rate_thursday", "rate_friday"]
    day_vals = [row[d] for d in days]
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if row["day_std"] > 0.25:
        low_day = day_names[int(np.argmin(day_vals))]
        return f"day_quirk ({low_day})"

    # Sudden mid-semester drop
    if row["mid_drop"] < -0.25:
        return "mid_semester_drop"

    # Late semester drop
    if row["late_drop"] < -0.25:
        return "late_semester_drop"

    # Long consecutive absence streak
    if row["max_streak"] >= 6:
        return "long_absence_streak"

    # Generally erratic (high weekly variance)
    if row["weekly_std"] > 0.35:
        return "erratic_attendance"

    # Chronic low attendance
    if row["overall_rate"] < 0.65:
        return "chronic_low"

    return "general_anomaly"


def generate_report(features_df, students_df, ground_truth_df):
    report = features_df.merge(
        students_df[["student_id", "roll_no", "full_name"]], on="student_id"
    )
    report = report.merge(
        ground_truth_df[["student_id", "type"]].rename(columns={"type": "true_archetype"}),
        on="student_id", how="left"
    )

    # Classify anomaly type
    report["anomaly_type"] = report.apply(classify_anomaly_type, axis=1)

    # Sort: anomalies first, then by raw score ascending (most anomalous first)
    report = report.sort_values(
        ["is_anomaly", "anomaly_raw_score"], ascending=[False, True]
    )

    # Save
    save_cols = [
        "student_id", "roll_no", "full_name", "true_archetype",
        "overall_rate", "day_std", "min_day_rate", "biggest_drop",
        "max_streak", "is_anomaly", "anomaly_type", "anomaly_raw_score",
    ]
    report[save_cols].to_csv(
        os.path.join(OUTPUT_DIR, "anomaly_detections.csv"), index=False
    )

    # Print anomalies
    anomalies = report[report["is_anomaly"] == 1]
    print(f"\n=== {len(anomalies)} ANOMALOUS ATTENDANCE PATTERNS DETECTED ===\n")
    print(f"{'Name':<25} {'Roll No':<22} {'True Type':<14} "
          f"{'Attendance':<11} {'Anomaly Type'}")
    print("-" * 95)
    for _, row in anomalies.iterrows():
        print(f"{row['full_name']:<25} {row['roll_no']:<22} "
              f"{row['true_archetype']:<14} "
              f"{row['overall_rate']:.1%}       "
              f"{row['anomaly_type']}")

    # Validation check
    print("\n=== VALIDATION AGAINST GROUND TRUTH ===")
    for archetype in ["declining", "chronic_low", "day_quirk", "reliable"]:
        subset = report[report["true_archetype"] == archetype]
        if len(subset) > 0:
            caught = subset["is_anomaly"].mean()
            print(f"{archetype:<15}: {caught:.1%} flagged as anomaly "
                  f"({len(subset)} students)")

    return report


def plot_anomalies(features_df, output_dir):
    """Scatter plot: overall rate vs weekly variance, colored by anomaly."""
    plt.figure(figsize=(9, 6))
    colors = features_df["is_anomaly"].map({0: "steelblue", 1: "crimson"})
    plt.scatter(
        features_df["overall_rate"],
        features_df["weekly_std"],
        c=colors, alpha=0.7, edgecolors="white", linewidth=0.5, s=60
    )
    plt.xlabel("Overall Attendance Rate")
    plt.ylabel("Weekly Attendance Std Dev (Erratic = High)")
    plt.title("Attendance Anomaly Detection\n(Red = Flagged Anomaly)")
    from matplotlib.patches import Patch
    legend = [Patch(color="steelblue", label="Normal"),
              Patch(color="crimson", label="Anomaly")]
    plt.legend(handles=legend)
    plt.tight_layout()
    path = os.path.join(output_dir, "anomaly_scatter.png")
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"Scatter plot saved: {path}")

    # Day-of-week heatmap for anomalous students
    day_cols = ["rate_monday", "rate_tuesday", "rate_wednesday",
                "rate_thursday", "rate_friday"]
    anomalies = features_df[features_df["is_anomaly"] == 1][day_cols].fillna(0)
    if len(anomalies) > 0:
        plt.figure(figsize=(8, max(4, len(anomalies) * 0.3)))
        sns_data = anomalies.head(25)  # top 25 anomalies
        plt.imshow(sns_data.values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        plt.colorbar(label="Attendance Rate")
        plt.xticks(range(5), ["Mon", "Tue", "Wed", "Thu", "Fri"])
        plt.yticks(range(len(sns_data)), [f"Student {i}" for i in range(len(sns_data))])
        plt.title("Day-of-Week Attendance Rates — Anomalous Students")
        plt.tight_layout()
        path2 = os.path.join(output_dir, "anomaly_day_heatmap.png")
        plt.savefig(path2, dpi=120)
        plt.close()
        print(f"Day heatmap saved: {path2}")


def main():
    print("=" * 55)
    print("ATTENDANCE PATTERN & ANOMALY DETECTOR")
    print("=" * 55)

    attendance, sessions, students, ground_truth = load_data()

    print("\nEngineering features...")
    features_df = engineer_anomaly_features(attendance, sessions)

    print("Running Isolation Forest anomaly detection...")
    features_df, model, scaler = detect_anomalies(features_df)

    print("\nGenerating report...")
    report = generate_report(features_df, students, ground_truth)

    print("\nGenerating charts...")
    try:
        import seaborn as sns
        plot_anomalies(features_df, OUTPUT_DIR)
    except Exception:
        plot_anomalies(features_df, OUTPUT_DIR)

    print(f"\nOutputs saved to: data/model_outputs/")
    print("\nDone! Model 2 complete.")


if __name__ == "__main__":
    main()