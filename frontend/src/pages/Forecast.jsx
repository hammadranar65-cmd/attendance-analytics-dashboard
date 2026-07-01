import { useState, useEffect } from "react";

export default function Forecast() {
  const [forecast, setForecast] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/forecast")
      .then(r => r.json()).then(setForecast);
  }, []);

  const trendClass = (t) =>
    t === "Declining" ? "trend-declining" :
    t === "Improving" ? "trend-improving" : "trend-stable";

  const trendIcon = (t) =>
    t === "Declining" ? "🔴" : t === "Improving" ? "🟢" : "🟡";

  return (
    <div>
      <h1 className="page-title">📈 Attendance Trend Forecast</h1>
      <div className="card">
        <h3>End-of-Semester Projections</h3>
        <table>
          <thead>
            <tr>
              <th>Course</th>
              <th>Current %</th>
              <th>Projected %</th>
              <th>Slope</th>
              <th>Trend</th>
            </tr>
          </thead>
          <tbody>
            {forecast.map((f, i) => (
              <tr key={i}>
                <td>{f.course_title}</td>
                <td>{(f.current_rate * 100).toFixed(1)}%</td>
                <td style={{fontWeight:700}}>{(f.projected_final * 100).toFixed(1)}%</td>
                <td style={{color: f.slope > 0 ? "#4ade80" : "#f87171"}}>
                  {f.slope > 0 ? "+" : ""}{f.slope.toFixed(4)}/week
                </td>
                <td>
                  <span className={trendClass(f.trend)}>
                    {trendIcon(f.trend)} {f.trend}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}