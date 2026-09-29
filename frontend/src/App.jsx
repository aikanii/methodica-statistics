import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useApp } from "./state.jsx";
import { Shell } from "./components.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Data from "./pages/Data.jsx";
import Explore from "./pages/Explore.jsx";
import Analyze from "./pages/Analyze.jsx";
import Models from "./pages/Models.jsx";
import Autopilot from "./pages/Autopilot.jsx";
import Insights from "./pages/Insights.jsx";
import Reports from "./pages/Reports.jsx";
import Settings from "./pages/Settings.jsx";

function Guard({ children }) {
  const { booting } = useApp();
  if (booting) {
    return (
      <div className="min-h-screen grid place-items-center text-pine">
        <div className="font-serif text-2xl">Methodica</div>
      </div>
    );
  }
  return <Shell>{children}</Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route
        path="/*"
        element={
          <Guard>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/data" element={<Data />} />
              <Route path="/explore" element={<Explore />} />
              <Route path="/analyze" element={<Analyze />} />
              <Route path="/models" element={<Models />} />
              <Route path="/autopilot" element={<Autopilot />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Guard>
        }
      />
    </Routes>
  );
}
