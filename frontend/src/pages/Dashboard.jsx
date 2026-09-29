import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../state.jsx";
import { Btn, Card, PageTitle } from "../components.jsx";

export default function Dashboard() {
  const { user, selectDataset } = useApp();
  const [data, setData] = useState(null);
  const nav = useNavigate();

  useEffect(() => {
    api.dashboard().then(setData).catch(() => {});
  }, []);

  const c = data?.counts || {};
  return (
    <div>
      <PageTitle
        kicker="Workspace"
        title="Open a dataset and ask a question."
        subtitle="Every conclusion in Methodica is tied to a dataset version, a method, and an assumption check you can inspect."
        actions={<Btn onClick={() => nav("/data")}>Open data</Btn>}
      />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          ["Projects", c.projects],
          ["Datasets", c.datasets],
          ["Analyses", c.analyses],
          ["Reports", c.reports],
        ].map(([k, v]) => (
          <Card key={k} className="p-4">
            <div className="text-[11px] uppercase tracking-wider text-ink/45">{k}</div>
            <div className="font-serif text-3xl mt-1">{v ?? "—"}</div>
          </Card>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-5">
        <Card className="p-5">
          <h2 className="font-serif text-xl mb-3">Datasets</h2>
          {(data?.datasets || []).length === 0 && (
            <p className="text-sm text-ink/60">
              Nothing loaded yet. Start from a sample (air quality, clinical trial, survey) on the Data page.
            </p>
          )}
          <ul className="space-y-2">
            {(data?.datasets || []).map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 text-sm border-b border-black/5 pb-2">
                <div>
                  <div className="font-medium">{d.name}</div>
                  <div className="text-ink/50 text-xs">
                    {d.n_rows} × {d.n_cols} · quality {d.quality_score ?? "—"}
                  </div>
                </div>
                <Btn
                  variant="ghost"
                  onClick={async () => {
                    await selectDataset(d.id);
                    nav("/data");
                  }}
                >
                  Open
                </Btn>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-5">
          <h2 className="font-serif text-xl mb-3">Recent analyses</h2>
          {(data?.analyses || []).length === 0 && <p className="text-sm text-ink/60">No analyses yet.</p>}
          <ul className="space-y-2">
            {(data?.analyses || []).map((a) => (
              <li key={a.id} className="text-sm border-b border-black/5 pb-2">
                <div className="font-medium">{a.method}</div>
                <div className="text-ink/50 text-xs truncate">{a.question || "Untitled"}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <Card className="p-5 mt-5">
        <h2 className="font-serif text-xl mb-2">How Methodica works</h2>
        <ol className="grid md:grid-cols-4 gap-3 text-sm mt-3">
          {[
            ["1. Evidence", "Profile and quality-check the table. Nothing is altered silently."],
            ["2. Method", "State a research question. The engine recommends a test and why."],
            ["3. Assumptions", "Normality, variance, cell counts, and design assumptions are screened."],
            ["4. Verdict", "You see the calculation, effect size, caveats, and a reproducible record."],
          ].map(([t, d]) => (
            <li key={t} className="rounded-xl bg-white border border-black/5 p-3">
              <div className="text-pine font-medium">{t}</div>
              <p className="text-ink/65 mt-1">{d}</p>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
