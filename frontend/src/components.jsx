import React, { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Bot,
  Database,
  FileText,
  FlaskConical,
  LayoutDashboard,
  Settings,
  Sparkles,
  Table2,
} from "lucide-react";
import { useApp } from "./state.jsx";

export function Logo({ compact }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-pine to-[#163a44] text-cream grid place-items-center font-serif text-lg">
        M
      </div>
      {!compact && (
        <div>
          <div className="font-serif text-[17px] leading-none text-cream">Methodica</div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/45 mt-0.5">evidence you can inspect</div>
        </div>
      )}
    </div>
  );
}

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/data", icon: Database, label: "Data" },
  { to: "/explore", icon: Table2, label: "Explore" },
  { to: "/analyze", icon: FlaskConical, label: "Analyze" },
  { to: "/models", icon: Activity, label: "Models" },
  { to: "/autopilot", icon: Sparkles, label: "Autopilot" },
  { to: "/insights", icon: Bot, label: "Insights" },
  { to: "/reports", icon: FileText, label: "Reports" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Shell({ children }) {
  const { user, dataset } = useApp();
  return (
    <div className="min-h-screen flex bg-paper">
      <aside className="w-[248px] shrink-0 bg-ink text-cream flex flex-col">
        <div className="px-5 py-5 border-b border-white/10">
          <Logo />
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13.5px] transition ${
                  isActive ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <n.icon size={16} strokeWidth={1.75} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-white/10">
          {dataset && (
            <div className="mb-3 rounded-lg bg-white/5 px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-white/40">Working dataset</div>
              <div className="text-xs mt-0.5 truncate">{dataset.name}</div>
              <div className="text-[11px] text-white/40">
                {dataset.n_rows?.toLocaleString()} × {dataset.n_cols} · v{dataset.version}
              </div>
            </div>
          )}
          <div className="min-w-0">
            <div className="text-xs truncate">{user?.name || "You"}</div>
            <div className="text-[11px] text-white/40 truncate">Local workspace · no sign-in</div>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <div className="max-w-[1280px] mx-auto px-8 py-7">{children}</div>
      </main>
    </div>
  );
}

export function PageTitle({ kicker, title, subtitle, actions }) {
  return (
    <div className="flex items-start justify-between gap-6 mb-6">
      <div>
        {kicker && <div className="text-[11px] uppercase tracking-[0.16em] text-pine/70 mb-1">{kicker}</div>}
        <h1 className="font-serif text-3xl text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-ink/60 mt-1 max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = "" }) {
  return <div className={`bg-cream border border-black/5 rounded-2xl shadow-card ${className}`}>{children}</div>;
}

export function Btn({ children, onClick, variant = "primary", type = "button", disabled, className = "" }) {
  const styles = {
    primary: "bg-pine text-white hover:bg-[#0c3d4a]",
    copper: "bg-copper text-white hover:bg-[#a74c1e]",
    ghost: "bg-white border border-black/10 hover:bg-mist text-ink",
    danger: "bg-red-700 text-white hover:bg-red-800",
  };
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`px-3.5 py-2 rounded-lg text-sm font-medium disabled:opacity-50 ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Field({ label, children }) {
  return (
    <label className="block">
      <div className="text-[11px] uppercase tracking-wider text-ink/50 mb-1">{label}</div>
      {children}
    </label>
  );
}

export function Select({ value, onChange, options, placeholder }) {
  return (
    <select
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-white border border-black/10 rounded-lg px-3 py-2 text-sm"
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value ?? o} value={o.value ?? o}>
          {o.label ?? o}
        </option>
      ))}
    </select>
  );
}

export function Input(props) {
  return (
    <input
      {...props}
      className={`w-full bg-white border border-black/10 rounded-lg px-3 py-2 text-sm ${props.className || ""}`}
    />
  );
}

export function StatusPill({ status }) {
  const map = {
    pass: "bg-emerald-50 text-emerald-800 border-emerald-200",
    fail: "bg-red-50 text-red-800 border-red-200",
    warning: "bg-amber-50 text-amber-900 border-amber-200",
    assumed: "bg-sky-50 text-sky-900 border-sky-200",
    info: "bg-slate-50 text-slate-700 border-slate-200",
    done: "bg-emerald-50 text-emerald-800 border-emerald-200",
    error: "bg-red-50 text-red-800 border-red-200",
    ready: "bg-pine/10 text-pine border-pine/20",
    awaiting_approval: "bg-amber-50 text-amber-900 border-amber-200",
    high: "bg-red-50 text-red-800 border-red-200",
    medium: "bg-amber-50 text-amber-900 border-amber-200",
    low: "bg-slate-50 text-slate-700 border-slate-200",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] border ${map[status] || map.info}`}>
      {status}
    </span>
  );
}

export function Plot({ spec, height = 380 }) {
  const ref = useRef(null);
  useEffect(() => {
    const Plotly = window.Plotly;
    if (!Plotly || !ref.current || !spec) return;
    const fig = spec.plotly || spec;
    Plotly.react(ref.current, fig.data || [], fig.layout || {}, { responsive: true, displaylogo: false });
    return () => {
      try {
        Plotly.purge(ref.current);
      } catch {}
    };
  }, [spec]);
  if (!spec) return null;
  return <div ref={ref} style={{ width: "100%", height }} />;
}

export function DataTable({ columns, rows, maxHeight = 420 }) {
  if (!columns?.length) return <div className="text-sm text-ink/50 p-4">No rows to display.</div>;
  return (
    <div className="overflow-auto scrollbar-thin border border-black/5 rounded-xl" style={{ maxHeight }}>
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 bg-mist/90 backdrop-blur">
          <tr>
            {columns.map((c) => (
              <th key={c} className="text-left font-medium px-3 py-2 border-b border-black/10 whitespace-nowrap">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(rows || []).map((r, i) => (
            <tr key={i} className="odd:bg-white even:bg-paper/40">
              {columns.map((c) => (
                <td key={c} className="px-3 py-1.5 border-b border-black/5 whitespace-nowrap font-mono text-[12px]">
                  {fmt(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function fmt(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : (+v).toPrecision(4);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function NeedDataset({ children }) {
  const { dataset } = useApp();
  const nav = useNavigate();
  if (!dataset) {
    return (
      <Card className="p-10 text-center">
        <BarChart3 className="mx-auto text-pine mb-3" />
        <h2 className="font-serif text-2xl">Select a dataset first</h2>
        <p className="text-sm text-ink/60 mt-2 mb-5">Upload a file or load a sample on the Data page.</p>
        <Btn onClick={() => nav("/data")}>Go to Data</Btn>
      </Card>
    );
  }
  return children;
}

export function ErrorBox({ err }) {
  if (!err) return null;
  const p = err.payload || {};
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-950">
      <div className="font-medium">{p.title || "Something went wrong"}</div>
      <div className="mt-1">{p.message || err.message}</div>
      {(p.technical || p.trace) && (
        <details className="mt-2 jsondetails">
          <summary className="text-xs text-red-800/70">Technical details</summary>
          <pre className="mt-2 text-[11px] whitespace-pre-wrap font-mono opacity-80">{p.technical || p.trace}</pre>
        </details>
      )}
    </div>
  );
}

export function StatGrid({ obj }) {
  if (!obj) return null;
  const entries = Object.entries(obj).filter(([, v]) => v === null || ["string", "number", "boolean"].includes(typeof v));
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {entries.map(([k, v]) => (
        <div key={k} className="rounded-xl bg-white border border-black/5 px-3 py-2">
          <div className="text-[10px] uppercase tracking-wider text-ink/45">{k.replaceAll("_", " ")}</div>
          <div className="font-mono text-sm mt-0.5">{fmt(v)}</div>
        </div>
      ))}
    </div>
  );
}

export function Flags({ flags }) {
  if (!flags?.length) return null;
  return (
    <div className="space-y-2">
      {flags.map((f, i) => (
        <div
          key={i}
          className={`rounded-xl px-3 py-2 text-sm border ${
            f.level === "error"
              ? "bg-red-50 border-red-200"
              : f.level === "warning"
              ? "bg-amber-50 border-amber-200"
              : "bg-sky-50 border-sky-200"
          }`}
        >
          <span className="font-medium mr-2">{f.level === "info" ? "ℹ️" : "⚠️"}</span>
          {f.message}
        </div>
      ))}
    </div>
  );
}

export function AssumptionTable({ checks }) {
  if (!checks?.length) return null;
  return (
    <div className="overflow-auto rounded-xl border border-black/5">
      <table className="w-full text-sm">
        <thead className="bg-mist">
          <tr>
            {["Assumption", "Status", "Evidence", "Recommended action"].map((h) => (
              <th key={h} className="text-left font-medium px-3 py-2">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {checks.map((c, i) => (
            <tr key={i} className="border-t border-black/5 align-top">
              <td className="px-3 py-2 font-medium">{c.name}</td>
              <td className="px-3 py-2">
                <StatusPill status={c.status} />
              </td>
              <td className="px-3 py-2 text-ink/70">{c.evidence}</td>
              <td className="px-3 py-2 text-ink/70">{c.recommended_action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
