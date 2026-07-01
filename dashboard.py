"""
dashboard.py — Attendance Analytics Dashboard (Streamlit)
Run with: streamlit run dashboard.py
"""

import os
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Attendance Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "model_outputs")


# ── Load Data ─────────────────────────────────────────────────
@st.cache_data
def load_all_data():
    attendance = pd.read_csv(os.path.join(DATA_DIR, "attendance_records.csv"))
    sessions = pd.read_csv(os.path.join(DATA_DIR, "sessions.csv"), parse_dates=["session_date"])
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv"))
    sections = pd.read_csv(os.path.join(DATA_DIR, "sections.csv"))
    courses = pd.read_csv(os.path.join(DATA_DIR, "courses.csv"))
    enrollments = pd.read_csv(os.path.join(DATA_DIR, "enrollments.csv"))

    min_date = sessions["session_date"].min()
    sessions["week_index"] = ((sessions["session_date"] - min_date).dt.days // 7)

    att = attendance.merge(
        sessions[["session_id", "week_index", "day_of_week", "section_id", "session_date"]],
        on="session_id"
    )
    att["present"] = (att["status"] != "absent").astype(int)
    att = att.merge(students[["student_id", "full_name", "roll_no"]], on="student_id")
    att = att.merge(sections[["section_id", "course_id", "section_label"]], on="section_id")
    att = att.merge(courses[["course_id", "course_title"]], on="course_id")

    return att, students, sections, courses, enrollments


@st.cache_data
def load_model_outputs():
    try:
        at_risk = pd.read_csv(os.path.join(OUTPUT_DIR, "at_risk_predictions.csv"))
        anomalies = pd.read_csv(os.path.join(OUTPUT_DIR, "anomaly_detections.csv"))
        forecast = pd.read_csv(os.path.join(OUTPUT_DIR, "forecast_summary.csv"))
        with open(os.path.join(OUTPUT_DIR, "ai_summaries.json")) as f:
            summaries = json.load(f)
        return at_risk, anomalies, forecast, summaries
    except FileNotFoundError:
        return None, None, None, None


# ── Sidebar ───────────────────────────────────────────────────
def sidebar(courses):
    st.sidebar.title("📊 Attendance Analytics")
    st.sidebar.markdown("**Emerson University Multan**")
    st.sidebar.markdown("BSCS — Fall 2026")
    st.sidebar.divider()

    role = st.sidebar.selectbox(
        "View as:",
        ["Instructor", "Department Head", "Admin"]
    )

    course_options = ["All Courses"] + list(courses["course_title"].unique())
    selected_course = st.sidebar.selectbox("Select Course:", course_options)

    return role, selected_course


# ── Overview Metrics ──────────────────────────────────────────
def show_overview(att, at_risk, anomalies):
    st.markdown("## 📊 Overview")

    total_students = att["student_id"].nunique()
    overall_rate = att["present"].mean()
    n_at_risk = len(at_risk[at_risk["predicted_at_risk"] == 1]) if at_risk is not None else 0
    n_anomalies = len(anomalies[anomalies["is_anomaly"] == 1]) if anomalies is not None else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Students", total_students)
    col2.metric("Overall Attendance", f"{overall_rate:.1%}",
                delta=f"{overall_rate - 0.75:.1%} vs threshold")
    col3.metric("At-Risk Students", n_at_risk,
                delta=f"{n_at_risk} need attention",
                delta_color="inverse")
    col4.metric("Anomalies Detected", n_anomalies,
                delta=f"{n_anomalies} unusual patterns",
                delta_color="inverse")


# ── Attendance Heatmap ────────────────────────────────────────
def show_heatmap(att, selected_course):
    st.markdown("## 🗓️ Attendance Heatmap (Week × Day)")

    if selected_course != "All Courses":
        att = att[att["course_title"] == selected_course]

    pivot = att.groupby(["week_index", "day_of_week"])["present"].mean().reset_index()
    pivot_table = pivot.pivot(index="day_of_week", columns="week_index", values="present")

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    pivot_table = pivot_table.reindex(
        [d for d in day_order if d in pivot_table.index]
    )

    fig = px.imshow(
        pivot_table,
        color_continuous_scale="RdYlGn",
        zmin=0, zmax=1,
        labels={"x": "Week", "y": "Day", "color": "Attendance Rate"},
        title=f"Attendance Rate by Week & Day — {selected_course}",
        aspect="auto",
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)


# ── Course Attendance Trend ───────────────────────────────────
def show_course_trends(att):
    st.markdown("## 📈 Course Attendance Trends")

    weekly = att.groupby(["course_title", "week_index"])["present"].mean().reset_index()

    fig = px.line(
        weekly, x="week_index", y="present",
        color="course_title",
        labels={"week_index": "Week", "present": "Attendance Rate",
                "course_title": "Course"},
        title="Weekly Attendance Rate per Course",
        markers=True,
    )
    fig.add_hline(y=0.75, line_dash="dash", line_color="red",
                  annotation_text="75% threshold")
    fig.update_layout(height=400, yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)


# ── At-Risk Students ──────────────────────────────────────────
def show_at_risk(at_risk):
    st.markdown("## ⚠️ At-Risk Students")

    if at_risk is None:
        st.warning("Run models/model_at_risk.py first to generate predictions.")
        return

    flagged = at_risk[at_risk["predicted_at_risk"] == 1].copy()
    flagged = flagged.sort_values("risk_probability", ascending=False)

    st.markdown(f"**{len(flagged)} students** are predicted to fall below the 75% threshold.")

    if len(flagged) > 0:
        display_cols = {
            "full_name": "Name",
            "roll_no": "Roll No",
            "overall_rate": "Current %",
            "projected_final": "Projected %",
            "risk_probability": "Risk Score",
        }
        display = flagged[list(display_cols.keys())].rename(columns=display_cols)
        display["Current %"] = display["Current %"].apply(lambda x: f"{x:.1%}")
        display["Projected %"] = display["Projected %"].apply(lambda x: f"{x:.1%}")
        display["Risk Score"] = display["Risk Score"].apply(lambda x: f"{x:.3f}")
        st.dataframe(display, use_container_width=True, height=300)

        fig = px.histogram(
            at_risk, x="risk_probability",
            color=at_risk["predicted_at_risk"].map({1: "At-Risk", 0: "Safe"}),
            nbins=20,
            labels={"risk_probability": "Risk Score", "color": "Status"},
            title="Risk Score Distribution",
            color_discrete_map={"At-Risk": "crimson", "Safe": "steelblue"},
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)


# ── Anomaly Detection ─────────────────────────────────────────
def show_anomalies(anomalies):
    st.markdown("## 🔍 Anomaly Detection")

    if anomalies is None:
        st.warning("Run models/model_anomaly.py first.")
        return

    flagged = anomalies[anomalies["is_anomaly"] == 1].copy()
    st.markdown(f"**{len(flagged)} students** show unusual absence patterns.")

    col1, col2 = st.columns(2)

    with col1:
        type_counts = flagged["anomaly_type"].value_counts().reset_index()
        type_counts.columns = ["Anomaly Type", "Count"]
        fig = px.bar(
            type_counts, x="Count", y="Anomaly Type",
            orientation="h",
            title="Anomaly Types Detected",
            color="Count",
            color_continuous_scale="Reds",
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig2 = px.scatter(
            anomalies,
            x="overall_rate", y="day_std",
            color=anomalies["is_anomaly"].map({1: "Anomaly", 0: "Normal"}),
            title="Anomaly Scatter: Attendance vs Day Variance",
            labels={"overall_rate": "Overall Rate", "day_std": "Day Variance"},
            color_discrete_map={"Anomaly": "crimson", "Normal": "steelblue"},
        )
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True)

    if len(flagged) > 0:
        display = flagged[["full_name", "roll_no", "overall_rate",
                            "anomaly_type", "max_streak"]].copy()
        display.columns = ["Name", "Roll No", "Attendance", "Pattern Type", "Max Absence Streak"]
        display["Attendance"] = display["Attendance"].apply(lambda x: f"{x:.1%}")
        st.dataframe(display, use_container_width=True, height=250)


# ── Forecast ──────────────────────────────────────────────────
def show_forecast(forecast):
    st.markdown("## 📉 Attendance Trend Forecast")

    if forecast is None:
        st.warning("Run models/model_forecast.py first.")
        return

    col1, col2 = st.columns(2)

    with col1:
        colors = {"Declining": "crimson", "Stable": "steelblue", "Improving": "green"}
        fig = go.Figure()
        for _, row in forecast.iterrows():
            fig.add_trace(go.Bar(
                x=[row["course_title"]],
                y=[row["projected_final"]],
                name=row["trend"],
                marker_color=colors.get(row["trend"], "grey"),
                showlegend=False,
            ))
        fig.add_hline(y=0.75, line_dash="dash", line_color="red",
                      annotation_text="75% threshold")
        fig.update_layout(
            title="Projected End-of-Semester Attendance",
            yaxis_tickformat=".0%",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        trend_colors = {"Declining": "🔴", "Stable": "🟡", "Improving": "🟢"}
        st.markdown("### Trend Summary")
        for _, row in forecast.iterrows():
            icon = trend_colors.get(row["trend"], "⚪")
            st.markdown(
                f"{icon} **{row['course_title']}** — "
                f"Current: {row['current_rate']:.1%} → "
                f"Projected: {row['projected_final']:.1%} "
                f"({row['trend']})"
            )


# ── AI Summaries ──────────────────────────────────────────────
def show_summaries(summaries):
    st.markdown("## 🤖 AI-Generated Insights")

    if summaries is None:
        st.warning("Run models/model_summary.py first.")
        return

    if "DEPARTMENT_OVERVIEW" in summaries:
        st.info(summaries["DEPARTMENT_OVERVIEW"])

    st.markdown("### Per-Course Summaries")
    for title, summary in summaries.items():
        if title == "DEPARTMENT_OVERVIEW":
            continue
        with st.expander(f"📚 {title}"):
            st.write(summary)


# ── Student Drill-Down ────────────────────────────────────────
def show_student_drilldown(att):
    st.markdown("## 👤 Student Drill-Down")

    student_names = sorted(att["full_name"].unique())
    selected = st.selectbox("Select a student:", student_names)

    if selected:
        student_att = att[att["full_name"] == selected]
        overall = student_att["present"].mean()
        roll_no = student_att["roll_no"].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Student", selected)
        col2.metric("Roll No", roll_no)
        col3.metric("Overall Attendance", f"{overall:.1%}",
                    delta="⚠ At Risk" if overall < 0.75 else "✓ Safe")

        weekly = student_att.groupby("week_index")["present"].mean().reset_index()
        fig = px.line(
            weekly, x="week_index", y="present",
            title=f"Weekly Attendance — {selected}",
            labels={"week_index": "Week", "present": "Attendance Rate"},
            markers=True,
        )
        fig.add_hline(y=0.75, line_dash="dash", line_color="red",
                      annotation_text="75% threshold")
        fig.update_layout(yaxis_tickformat=".0%", height=300)
        st.plotly_chart(fig, use_container_width=True)

        course_att = student_att.groupby("course_title")["present"].mean().reset_index()
        course_att.columns = ["Course", "Attendance Rate"]
        fig2 = px.bar(
            course_att, x="Course", y="Attendance Rate",
            title=f"Attendance by Course — {selected}",
            color="Attendance Rate",
            color_continuous_scale="RdYlGn",
        )
        fig2.add_hline(y=0.75, line_dash="dash", line_color="red")
        fig2.update_layout(yaxis_tickformat=".0%", height=300)
        st.plotly_chart(fig2, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────
def main():
    att, students, sections, courses, enrollments = load_all_data()
    at_risk, anomalies, forecast, summaries = load_model_outputs()

    role, selected_course = sidebar(courses)

    st.title("📊 Attendance Analytics Dashboard")
    st.markdown(
        f"**Emerson University Multan** | BSCS Evening | Fall 2026 | "
        f"Viewing as: `{role}`"
    )
    st.divider()

    filtered_att = att if selected_course == "All Courses" else \
        att[att["course_title"] == selected_course]

    show_overview(filtered_att, at_risk, anomalies)
    st.divider()

    show_heatmap(att, selected_course)
    st.divider()

    show_course_trends(att)
    st.divider()

    show_at_risk(at_risk)
    st.divider()

    show_anomalies(anomalies)
    st.divider()

    show_forecast(forecast)
    st.divider()

    show_summaries(summaries)
    st.divider()

    show_student_drilldown(att)


if __name__ == "__main__":
    main()
    