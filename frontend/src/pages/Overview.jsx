import { useState, useEffect } from "react";

export default function Overview() {
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState([]);

  useEffect(() => {
    fetch("http://https://attendance-api-3uy0.onrender.com/api/overview")
      .then(r => r.json()).then(setOverview);
    fetch("http://https://attendance-api-3uy0.onrender.com/api/weekly-trends")
      .then(r => r.json()).then(setTrends);
  }, []);

  const courses = [...new Set(trends.map(t => t.course_title))];
  const weeks = [...new Set(trends.map(t => t.week_index))].sort((a,b)=>a-b);

  return (
    <div>
      <h1 className="page-title">📊 Overview</h1>

      {overview && (
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="label">Total Students</div>
            <div className="value">{overview.total_students}</div>
          </div>
          <div className="metric-card">
            <div className="label">Overall Attendance</div>
            <div className="value">{(overview.overall_rate * 100).toFixed(1)}%</div>
            <div className="delta">vs 75% threshold</div>
          </div>
          <div className="metric-card">
            <div className="label">At-Risk Students</div>
            <div className="value" style={{color:"#f87171"}}>{overview.at_risk_count}</div>
            <div className="delta">need attention</div>
          </div>
          <div className="metric-card">
            <div className="label">Anomalies Detected</div>
            <div className="value" style={{color:"#facc15"}}>{overview.anomaly_count}</div>
            <div className="delta">unusual patterns</div>
          </div>
        </div>
      )}

      <div className="card">
        <h3>📈 Weekly Attendance by Course</h3>
        <div style={{overflowX:"auto"}}>
          <table>
            <thead>
              <tr>
                <th>Course</th>
                {weeks.map(w => <th key={w}>W{w}</th>)}
              </tr>
            </thead>
            <tbody>
              {courses.map(course => (
                <tr key={course}>
                  <td>{course}</td>
                  {weeks.map(w => {
                    const entry = trends.find(
                      t => t.course_title === course && t.week_index === w
                    );
                    const rate = entry ? entry.present : null;
                    const color = rate === null ? "#475569"
                      : rate >= 0.85 ? "#4ade80"
                      : rate >= 0.75 ? "#facc15" : "#f87171";
                    return (
                      <td key={w} style={{color, fontWeight:600}}>
                        {rate !== null ? `${(rate*100).toFixed(0)}%` : "-"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}