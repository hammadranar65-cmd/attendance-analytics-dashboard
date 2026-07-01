import { useState } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Overview from "./pages/Overview";
import AtRisk from "./pages/AtRisk";
import Anomalies from "./pages/Anomalies";
import Forecast from "./pages/Forecast";
import Summaries from "./pages/Summaries";
import StudentDetail from "./pages/StudentDetail";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <div className="logo">
            <h2>📊 Attendance</h2>
            <p>Emerson University</p>
          </div>
          <NavLink to="/" end>🏠 Overview</NavLink>
          <NavLink to="/at-risk">⚠️ At-Risk</NavLink>
          <NavLink to="/anomalies">🔍 Anomalies</NavLink>
          <NavLink to="/forecast">📈 Forecast</NavLink>
          <NavLink to="/summaries">🤖 AI Summaries</NavLink>
          <NavLink to="/students">👤 Students</NavLink>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/at-risk" element={<AtRisk />} />
            <Route path="/anomalies" element={<Anomalies />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/summaries" element={<Summaries />} />
            <Route path="/students" element={<StudentDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;