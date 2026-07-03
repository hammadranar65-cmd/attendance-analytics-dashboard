import { useState, useEffect } from "react";

export default function StudentDetail() {
  const [students, setStudents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    fetch("https://attendance-api-3uy0.onrender.com/api/students")
      .then(r => r.json()).then(setStudents);
  }, []);

  useEffect(() => {
    if (selected) {
      fetch(`https://attendance-api-3uy0.onrender.com/api/student/${selected}`)
        .then(r => r.json()).then(setDetail);
    }
  }, [selected]);

  return (
    <div>
      <h1 className="page-title">👤 Student Drill-Down</h1>

      <div className="card">
        <h3>Select a Student</h3>
        <select onChange={e => setSelected(e.target.value)} defaultValue="">
          <option value="" disabled>Choose a student...</option>
          {students.map(s => (
            <option key={s.student_id} value={s.student_id}>
              {s.full_name} ({s.roll_no})
            </option>
          ))}
        </select>
      </div>

      {detail && (
        <>
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="label">Name</div>
              <div className="value" style={{fontSize:18}}>{detail.full_name}</div>
            </div>
            <div className="metric-card">
              <div className="label">Roll No</div>
              <div className="value" style={{fontSize:18}}>{detail.roll_no}</div>
            </div>
            <div className="metric-card">
              <div className="label">Overall Attendance</div>
              <div className="value"
                style={{color: detail.overall_rate < 0.75 ? "#f87171" : "#4ade80"}}>
                {(detail.overall_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div className="metric-card">
              <div className="label">Status</div>
              <div className="value" style={{fontSize:16}}>
                {detail.overall_rate < 0.75
                  ? <span className="badge badge-danger">At Risk</span>
                  : <span className="badge badge-success">Safe</span>}
              </div>
            </div>
          </div>

          <div className="card">
            <h3>Weekly Attendance Trend</h3>
            <table>
              <thead>
                <tr><th>Week</th><th>Attendance Rate</th><th>Status</th></tr>
              </thead>
              <tbody>
                {detail.weekly.map((w, i) => (
                  <tr key={i}>
                    <td>Week {w.week}</td>
                    <td style={{
                      color: w.rate >= 0.85 ? "#4ade80"
                           : w.rate >= 0.75 ? "#facc15" : "#f87171",
                      fontWeight: 600
                    }}>
                      {(w.rate * 100).toFixed(1)}%
                    </td>
                    <td>
                      {w.rate >= 0.75
                        ? <span className="badge badge-success">OK</span>
                        : <span className="badge badge-danger">Low</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3>Attendance by Course</h3>
            <table>
              <thead>
                <tr><th>Course</th><th>Attendance Rate</th><th>Status</th></tr>
              </thead>
              <tbody>
                {detail.by_course.map((c, i) => (
                  <tr key={i}>
                    <td>{c.course}</td>
                    <td style={{
                      color: c.rate >= 0.85 ? "#4ade80"
                           : c.rate >= 0.75 ? "#facc15" : "#f87171",
                      fontWeight: 600
                    }}>
                      {(c.rate * 100).toFixed(1)}%
                    </td>
                    <td>
                      {c.rate >= 0.75
                        ? <span className="badge badge-success">OK</span>
                        : <span className="badge badge-danger">Low</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}