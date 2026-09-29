import React, { useState } from "react";
import { api } from "../api";
import { useApp } from "../state.jsx";
import { Btn, Card, ErrorBox, NeedDataset, PageTitle } from "../components.jsx";

const PROMPTS = [
  "What are the most important patterns?",
  "Which variables are correlated?",
  "Are there significant differences between groups?",
  "Which statistical test should I use?",
  "Find unusual observations.",
  "What assumptions were violated?",
  "Create a regression model.",
];

export default function Insights() {
  const { datasetId } = useApp();
  const [q, setQ] = useState("What are the most important patterns?");
  const [conv, setConv] = useState([]);
  const [cid, setCid] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  async function send(text) {
    const question = text || q;
    setBusy(true);
    setErr(null);
    setConv((c) => [...c, { role: "user", content: question }]);
    try {
      const res = await api.assistant(datasetId, { question, conversation_id: cid });
      setCid(res.conversation_id);
      setConv((c) => [...c, res]);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <NeedDataset>
      <PageTitle
        kicker="Insights"
        title="Statistical assistant"
        subtitle="I only quote numbers I compute. If I cannot run a test, I will say so — I will not fabricate a p-value."
      />
      <ErrorBox err={err} />
      <div className="flex flex-wrap gap-2 mb-4">
        {PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => {
              setQ(p);
              send(p);
            }}
            className="text-xs px-2.5 py-1 rounded-full bg-white border border-black/10 hover:border-pine"
          >
            {p}
          </button>
        ))}
      </div>
      <Card className="p-5 min-h-[360px] space-y-3">
        {conv.length === 0 && (
          <p className="text-sm text-ink/55">Ask about this dataset. Conclusions always reference computed output.</p>
        )}
        {conv.map((m, i) => (
          <div key={i} className={`text-sm leading-relaxed ${m.role === "user" ? "text-ink/80" : ""}`}>
            <div className="text-[10px] uppercase tracking-wider text-ink/40 mb-1">{m.role}</div>
            <div className={m.role === "assistant" ? "bg-white rounded-xl p-3 border border-black/5" : ""}>
              {m.content}
            </div>
            {m.citations?.length > 0 && (
              <div className="text-[11px] text-ink/45 mt-1">Grounded in {m.citations.map((c) => c.kind).join(", ")}</div>
            )}
          </div>
        ))}
      </Card>
      <div className="flex gap-2 mt-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          className="flex-1 bg-white border border-black/10 rounded-lg px-3 py-2 text-sm"
          placeholder="Ask a question…"
        />
        <Btn onClick={() => send()} disabled={busy}>
          {busy ? "Computing…" : "Ask"}
        </Btn>
      </div>
    </NeedDataset>
  );
}
