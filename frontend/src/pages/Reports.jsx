import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state.jsx";
import { Btn, Card, ErrorBox, Field, NeedDataset, PageTitle, Select } from "../components.jsx";

export default function Reports() {
  const { datasetId, lastAnalysis } = useApp();
  const [style, setStyle] = useState("academic");
  const [fmt, setFmt] = useState("html");
  const [question, setQuestion] = useState("");
  const [err, setErr] = useState(null);
  const [out, setOut] = useState(null);
  const [list, setList] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.reports().then(setList).catch(() => {});
  }, [out]);

  async function generate() {
    setBusy(true);
    setErr(null);
    try {
      const body = {
        style,
        format: fmt,
        question: question || lastAnalysis?.question || "",
        analysis: lastAnalysis?.result || lastAnalysis?.analysis,
        recommendation: lastAnalysis?.recommendation,
        assumptions: lastAnalysis?.assumptions,
        validation: lastAnalysis?.validation,
        analysis_id: lastAnalysis?.analysis_id,
      };
      const res = await api.report(datasetId, body);
      setOut(res);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <NeedDataset>
      <PageTitle
        kicker="Reports"
        title="Reproducible reporting"
        subtitle="Academic, business, scientific, or general. Every figure of merit comes from the analysis engine."
      />
      <ErrorBox err={err} />
      <Card className="p-5 mb-5">
        <Field label="Research question (used if no analysis is in memory)">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="w-full bg-white border border-black/10 rounded-xl px-3 py-2 text-sm min-h-[70px]"
          />
        </Field>
        <div className="grid md:grid-cols-3 gap-3 mt-3">
          <Field label="Style">
            <Select value={style} onChange={setStyle} options={["academic", "business", "scientific", "general"]} />
          </Field>
          <Field label="Format">
            <Select value={fmt} onChange={setFmt} options={["html", "md", "docx", "pdf", "xlsx", "csv", "json"]} />
          </Field>
          <div className="flex items-end">
            <Btn onClick={generate} disabled={busy}>
              {busy ? "Writing…" : "Generate report"}
            </Btn>
          </div>
        </div>
      </Card>
      {out && (
        <Card className="p-5 mb-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-serif text-xl">{out.title}</div>
              <div className="text-xs text-ink/50">{out.format}</div>
            </div>
            <a className="text-sm text-pine underline" href={out.download}>
              Download
            </a>
          </div>
          {out.markdown && (
            <pre className="mt-4 text-xs whitespace-pre-wrap bg-white rounded-xl p-4 border border-black/5 max-h-[480px] overflow-auto">
              {out.markdown}
            </pre>
          )}
        </Card>
      )}
      <h2 className="font-serif text-xl mb-2">Previous reports</h2>
      <div className="space-y-2">
        {list.map((r) => (
          <Card key={r.id} className="p-3 flex items-center justify-between text-sm">
            <div>
              <div className="font-medium">{r.title}</div>
              <div className="text-xs text-ink/45">
                {r.style} · {r.format} · {r.created_at}
              </div>
            </div>
            <a className="text-pine underline" href={`/api/reports/${r.id}/download`}>
              Download
            </a>
          </Card>
        ))}
      </div>
    </NeedDataset>
  );
}
