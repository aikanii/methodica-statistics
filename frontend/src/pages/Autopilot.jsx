import React, { useState } from "react";
import { api } from "../api";
import { useApp } from "../state.jsx";
import {
  AssumptionTable,
  Btn,
  Card,
  ErrorBox,
  Flags,
  NeedDataset,
  PageTitle,
  Plot,
  StatusPill,
} from "../components.jsx";

export default function Autopilot() {
  const { datasetId, setLastAnalysis } = useApp();
  const [question, setQuestion] = useState("Is there a relationship between temperature and PM2.5?");
  const [out, setOut] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setErr(null);
    try {
      const res = await api.autopilot(datasetId, { question });
      setOut(res);
      setLastAnalysis(res);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <NeedDataset>
      <PageTitle
        kicker="Autopilot"
        title="From question to reproducible result"
        subtitle="Every step is visible. Cleaning is proposed, never silent. You can override the method on the Analyze page."
      />
      <Card className="p-5 mb-5">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="w-full bg-white border border-black/10 rounded-xl px-3 py-2 text-sm min-h-[80px]"
        />
        <Btn className="mt-3" onClick={run} disabled={busy}>
          {busy ? "Running pipeline…" : "Run autopilot"}
        </Btn>
      </Card>
      <ErrorBox err={err} />
      {out && (
        <div className="grid md:grid-cols-[280px_1fr] gap-5">
          <div className="space-y-2">
            {(out.steps || []).map((s, i) => (
              <div key={s.key} className="flex items-start gap-2 text-sm">
                <div className="mt-1 h-2 w-2 rounded-full bg-pine shrink-0" />
                <div>
                  <div className="font-medium">
                    {i + 1}. {s.title} <StatusPill status={s.status} />
                  </div>
                  {s.note && <div className="text-xs text-ink/50">{s.note}</div>}
                </div>
              </div>
            ))}
          </div>
          <div className="space-y-4">
            <Card className="p-5">
              <div className="text-[11px] uppercase tracking-wider text-pine">Selected method</div>
              <h2 className="font-serif text-2xl">{out.recommendation?.recommended_label}</h2>
              <ul className="mt-2 text-sm space-y-1">
                {(out.recommendation?.why || []).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </Card>
            {out.cleaning_proposals?.length > 0 && (
              <Card className="p-4">
                <div className="italic text-sm mb-2">The system proposes these changes.</div>
                {out.cleaning_proposals.slice(0, 8).map((p, i) => (
                  <div key={i} className="text-xs text-ink/70">
                    {p.operation} {p.column || ""} — {p.problem}
                  </div>
                ))}
              </Card>
            )}
            <AssumptionTable checks={out.assumptions} />
            <Flags flags={out.validation?.flags} />
            <Card className="p-5">
              <p className="font-serif text-xl">{out.analysis?.summary}</p>
              <p className="text-sm text-ink/70 mt-3">{out.interpretation}</p>
            </Card>
            {(out.charts || []).slice(0, 2).map((c, i) => (
              <Card key={i} className="p-3">
                <Plot spec={c} />
              </Card>
            ))}
          </div>
        </div>
      )}
    </NeedDataset>
  );
}
