import { useState, useEffect } from "react";

export default function Anomalies() {
  const [anomalies, setAnomalies] = useState([]);

  useEffect(() => {
    fetch("https://attendance-api-3uy0.onrender.com/api/anomalies")
      .then(r => r.json()).then(setAnomalies);
  }, []);

  return (
    <div>
      <h1 className="page-title">🔍 Anomaly Detection</h1>
      <div className="card">
        <h3>{anomalies.length} students with unusual absence patterns</h3>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Roll No</th>
              <th>Attendance</th>
              <th>Pattern Type</th>
              <th>Max Streak</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.map((a, i) => (
              <tr key={i}>
                <td>{a.full_name}</td>
                <td>{a.roll_no}</td>
                <td>{(a.overall_rate * 100).toFixed(1)}%</td>
                <td><span className="badge badge-warning">{a.anomaly_type}</span></td>
                <td>{a.max_streak} sessions</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}