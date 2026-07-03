import { useState, useEffect } from "react";

export default function AtRisk() {
  const [students, setStudents] = useState([]);

  useEffect(() => {
    fetch("https://attendance-api-3uy0.onrender.com/api/at-risk")
      .then(r => r.json()).then(setStudents);
  }, []);

  return (
    <div>
      <h1 className="page-title">⚠️ At-Risk Students</h1>
      <div className="card">
        <h3>{students.length} students predicted to fall below 75% threshold</h3>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Roll No</th>
              <th>Current %</th>
              <th>Projected %</th>
              <th>Risk Score</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {students.map((s, i) => (
              <tr key={i}>
                <td>{s.full_name}</td>
                <td>{s.roll_no}</td>
                <td>{(s.overall_rate * 100).toFixed(1)}%</td>
                <td>{(s.projected_final * 100).toFixed(1)}%</td>
                <td>
                  <div className="risk-bar-wrap">
                    <div className="risk-bar" style={{width: `${s.risk_probability * 100}%`}} />
                  </div>
                  <span style={{fontSize:12, color:"#94a3b8"}}>{s.risk_probability.toFixed(3)}</span>
                </td>
                <td><span className="badge badge-danger">At Risk</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}