import { useState, useEffect } from "react";

export default function Summaries() {
  const [summaries, setSummaries] = useState({});

  useEffect(() => {
    fetch("https://attendance-api-3uy0.onrender.com/api/summaries")
      .then(r => r.json()).then(setSummaries);
  }, []);

  return (
    <div>
      <h1 className="page-title">🤖 AI-Generated Insights</h1>

      {summaries.DEPARTMENT_OVERVIEW && (
        <div className="card">
          <h3>Department Overview</h3>
          <div className="summary-box">{summaries.DEPARTMENT_OVERVIEW}</div>
        </div>
      )}

      <div className="card">
        <h3>Per-Course Summaries</h3>
        {Object.entries(summaries)
          .filter(([k]) => k !== "DEPARTMENT_OVERVIEW")
          .map(([title, summary]) => (
            <div key={title} style={{marginBottom: 16}}>
              <h4 style={{color:"#38bdf8", marginBottom:8}}>📚 {title}</h4>
              <div className="summary-box">{summary}</div>
            </div>
          ))}
      </div>
    </div>
  );
}