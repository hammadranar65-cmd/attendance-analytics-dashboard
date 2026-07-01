"""
model_at_risk.py — At-Risk Student Prediction Model
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report
import matplotlib.pyplot as plt

OBSERVATION_WEEK = 8
TOTAL_WEEKS = 16
AT_RISK_THRESHOLD = 0.75
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "model_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_data():
    print("Loading data from CSV files...")
    attendance = pd.read_csv(os.path.join(DATA_DIR, "attendance_records.csv"))
    sessions = pd.read_csv(os.path.join(DATA_DIR, "sessions.csv"), parse_dates=["session_date"])
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    enrollments = pd.read_csv(os.path.join(DATA_DIR, "enrollments.csv"))
    ground_truth = pd.read_csv(os.path.join(DATA_DIR, "_ground_truth_archetypes.csv"))
    return attendance, sessions, students, enrollments, ground_truth


def add_week_index(sessions_df):
    sessions_df = sessions_df.copy()
    min_date = sessions_df["session_date"].min()
    sessions_df["week_index"] = ((sessions_df["session_date"] - min_date).dt.days // 7)
    return sessions_df


def engineer_features(attendance, sessions, enrollments, observation_week):
    sessions = add_week_index(sessions)
    att_full = attendance.merge(
        sessions[["session_id", "week_index", "day_of_week", "section_id"]], on="session_id"
    )
    att_full["present"] = (att_full["status"] != "absent").astype(int)
    att_observed = att_full[att_full["week_index"] < observation_week].copy()

    features_list = []

    for student_id in attendance["student_id"].unique():
        s_obs = att_observed[att_observed["student_id"] == student_id]
        if len(s_obs) == 0:
            continue

        overall_rate = s_obs["present"].mean()
        recent = s_obs[s_obs["week_index"] >= observation_week - 3]
        recent_rate = recent["present"].mean() if len(recent) > 0 else overall_rate
        early = s_obs[s_obs["week_index"] < 3]
        early_rate = early["present"].mean() if len(early) > 0 else overall_rate
        rate_of_change = recent_rate - early_rate

        sorted_records = s_obs.sort_values("week_index")
        max_consec_absent = 0
        current_streak = 0
        for _, row in sorted_records.iterrows():
            if row["present"] == 0:
                current_streak += 1
                max_consec_absent = max(max_consec_absent, current_streak)
            else:
                current_streak = 0

        weekly_rates = s_obs.groupby("week_index")["present"].mean()
        if len(weekly_rates) >= 3:
            x = np.array(weekly_rates.index)
            y = np.array(weekly_rates.values)
            slope = np.polyfit(x, y, 1)[0]
        else:
            slope = 0.0

        day_rates = s_obs.groupby("day_of_week")["present"].mean()
        min_day_rate = day_rates.min() if len(day_rates) > 0 else overall_rate
        day_rate_std = day_rates.std() if len(day_rates) > 1 else 0.0

        weeks_remaining = TOTAL_WEEKS - observation_week
        projected_final = float(np.clip(overall_rate + (slope * weeks_remaining), 0, 1))
        n_courses = s_obs["section_id"].nunique()

        final_rate = att_full[att_full["student_id"] == student_id]["present"].mean()
        is_at_risk = int(final_rate < AT_RISK_THRESHOLD)

        features_list.append({
            "student_id": student_id,
            "overall_rate": overall_rate,
            "recent_rate": recent_rate,
            "early_rate": early_rate,
            "rate_of_change": rate_of_change,
            "slope": slope,
            "max_consec_absent": max_consec_absent,
            "min_day_rate": min_day_rate,
            "day_rate_std": day_rate_std,
            "projected_final": projected_final,
            "n_courses": n_courses,
            "is_at_risk": is_at_risk,
        })

    return pd.DataFrame(features_list)


FEATURE_COLS = [
    "overall_rate", "recent_rate", "early_rate", "rate_of_change",
    "slope", "max_consec_absent", "min_day_rate", "day_rate_std",
    "projected_final", "n_courses",
]


def train_and_evaluate(features_df):
    X = features_df[FEATURE_COLS].fillna(0)
    y = features_df["is_at_risk"]

    print(f"\nDataset: {len(features_df)} students, "
          f"{y.sum()} at-risk ({y.mean():.1%}), "
          f"{(1-y).sum()} safe ({(1-y.mean()):.1%})")

    model = RandomForestClassifier(
        n_estimators=200, max_depth=6, min_samples_leaf=3,
        class_weight="balanced", random_state=42,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="recall")
    print(f"\nCross-validation Recall: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    model.fit(X, y)
    y_pred = model.predict(X)
    print("\nClassification Report:")
    print(classification_report(y, y_pred, target_names=["Safe", "At-Risk"]))
    return model


def generate_report(model, features_df, students_df, ground_truth_df):
    X = features_df[FEATURE_COLS].fillna(0)
    features_df = features_df.copy()
    features_df["predicted_at_risk"] = model.predict(X)
    features_df["risk_probability"] = model.predict_proba(X)[:, 1]

    report = features_df.merge(students_df[["student_id", "roll_no", "full_name"]], on="student_id")
    report = report.merge(
        ground_truth_df[["student_id", "type"]].rename(columns={"type": "true_archetype"}),
        on="student_id", how="left"
    )
    report = report.sort_values("risk_probability", ascending=False)

    report.to_csv(os.path.join(OUTPUT_DIR, "at_risk_predictions.csv"), index=False)

    print("\n=== TOP 20 HIGHEST-RISK STUDENTS ===")
    print(f"{'Name':<25} {'Roll No':<22} {'Current%':<10} {'Projected%':<12} {'Risk':<8} {'Flagged'}")
    print("-" * 85)
    for _, row in report.head(20).iterrows():
        flagged = "YES" if row["predicted_at_risk"] else "no"
        print(f"{row['full_name']:<25} {row['roll_no']:<22} "
              f"{row['overall_rate']:.1%}      "
              f"{row['projected_final']:.1%}         "
              f"{row['risk_probability']:.3f}   {flagged}")

    print("\n=== VALIDATION AGAINST GROUND TRUTH ===")
    for archetype in ["declining", "chronic_low", "day_quirk", "reliable"]:
        subset = report[report["true_archetype"] == archetype]
        if len(subset) > 0:
            caught = subset["predicted_at_risk"].mean()
            print(f"{archetype:<15}: {caught:.1%} flagged ({len(subset)} students)")


def plot_importance(model):
    importance_df = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=True)

    plt.figure(figsize=(8, 5))
    plt.barh(importance_df["feature"], importance_df["importance"], color="steelblue")
    plt.xlabel("Importance")
    plt.title("At-Risk Prediction — Feature Importance")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "at_risk_feature_importance.png")
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"\nChart saved: {path}")


def main():
    print("=" * 55)
    print("AT-RISK STUDENT PREDICTION MODEL")
    print(f"Observation: Week {OBSERVATION_WEEK} of {TOTAL_WEEKS}")
    print(f"Threshold: < {AT_RISK_THRESHOLD:.0%} attendance = at risk")
    print("=" * 55)

    attendance, sessions, students, enrollments, ground_truth = load_data()

    print("\nEngineering features...")
    features_df = engineer_features(attendance, sessions, enrollments, OBSERVATION_WEEK)

    print("\nTraining model...")
    model = train_and_evaluate(features_df)

    print("\nGenerating report...")
    generate_report(model, features_df, students, ground_truth)

    print("\nPlotting feature importance...")
    plot_importance(model)

    print(f"\nOutputs saved to: data/model_outputs/")
    print("\nDone! Model 1 complete.")


if __name__ == "__main__":
    main()