import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state.jsx";
import {
  AssumptionTable,
  Btn,
  Card,
  ErrorBox,
  Field,
  Flags,
  NeedDataset,
  PageTitle,
  Plot,
  Select,
  StatGrid,
} from "../components.jsx";

export default function Analyze() {
  const { datasetId, profile, setLastAnalysis } = useApp();
  const [question, setQuestion] = useState(
    "Is there a significant difference in PM2.5 levels between urban and rural monitoring locations?"
  );
  const [rec, setRec] = useState(null);
  const [method, setMethod] = useState("");
  const [methods, setMethods] = useState([]);
  const [y, setY] = useState("");
  const [x, setX] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [out, setOut] = useState(null);

  useEffect(() => {
    api.methods().then(setMethods).catch(() => {});
  }, []);

  const cols = profile?.columns?.map((c) => c.name) || [];
  const families = [...new Set(methods.map((m) => m.family))];

  async function recommend() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.recommend(datasetId, { question });
      setRec(r);
      setMethod(r.recommended);
      setY(r.dependent || "");
      setX(typeof r.independent === "string" ? r.independent : "");
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    setBusy(true);
    setErr(null);
    try {
      const params = buildParams(method, y, x, rec);
      const res = await api.analyze(datasetId, { method, params, question });
      setOut(res);
      setLastAnalysis({ ...res, question, method });
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <NeedDataset>
      <PageTitle
        kicker="Analyze"
        title="Research question"
        subtitle="You do not need to know the test. Describe what you want to know; inspect and override the recommendation."
      />
      <ErrorBox err={err} />
      <Card className="p-5 mb-5">
        <Field label="What do you want to know?">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="w-full bg-white border border-black/10 rounded-xl px-3 py-2 text-sm min-h-[88px]"
          />
        </Field>
        <div className="flex gap-2 mt-3">
          <Btn onClick={recommend} disabled={busy}>
            Recommend a method
          </Btn>
          <Btn variant="ghost" onClick={run} disabled={busy || !method}>
            Run analysis
          </Btn>
        </div>
      </Card>

      {rec && (
        <Card className="p-5 mb-5">
          <div className="text-[11px] uppercase tracking-wider text-pine">Recommended analysis</div>
          <h2 className="font-serif text-2xl mt-1">{rec.recommended_label}</h2>
          <ul className="mt-3 space-y-1 text-sm">
            {(rec.why || []).map((w, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-pine">▸</span>
                {w}
              </li>
            ))}
          </ul>
          {rec.alternatives?.length > 0 && (
            <div className="mt-3 text-sm">
              <span className="font-medium">Alternatives · </span>
              {rec.alternatives.map((a, i) => (
                <button key={i} className="underline text-pine mr-3" onClick={() => setMethod(a.method)}>
                  {a.method}
                </button>
              ))}
            </div>
          )}
          <div className="grid md:grid-cols-3 gap-3 mt-4">
            <Field label="Method (override)">
              <select
                className="w-full bg-white border border-black/10 rounded-lg px-3 py-2 text-sm"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              >
                {families.map((f) => (
                  <optgroup key={f} label={f}>
                    {methods
                      .filter((m) => m.family === f)
                      .map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
            </Field>
            <Field label="Outcome (y)">
              <Select value={y} onChange={setY} options={cols} placeholder="—" />
            </Field>
            <Field label="Predictor / group (x)">
              <Select value={x} onChange={setX} options={cols} placeholder="—" />
            </Field>
          </div>
        </Card>
      )}

      {out && <ResultPane out={out} />}
    </NeedDataset>
  );
}

function buildParams(method, y, x, rec) {
  const base = { ...(rec?.params || {}), y, x };
  if (["pearson", "spearman", "kendall", "paired_t", "wilcoxon", "chi_square", "fisher_exact"].includes(method)) {
    return { x, y };
  }
  if (["independent_t", "mannwhitney", "oneway_anova", "kruskal", "tukey_hsd", "levene", "permutation_test"].includes(method)) {
    return { y, x, levels: rec?.params?.levels };
  }
  if (["linear_regression", "multiple_regression", "robust_regression", "logistic_regression", "poisson_regression"].includes(method)) {
    return { y, x: x ? [x] : rec?.params?.x };
  }
  if (method === "descriptive") return { columns: y ? [y] : rec?.params?.columns };
  if (method === "frequency" || method === "shapiro_wilk") return { column: y || x };
  return base;
}

export function ResultPane({ out }) {
  const r = out.result || {};
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="text-[11px] uppercase tracking-wider text-pine">{r.method_label || r.method}</div>
        <p className="font-serif text-2xl mt-1 leading-snug">{r.summary}</p>
        <p className="text-sm text-ink/70 mt-3 leading-relaxed">{r.interpretation}</p>
        {r.formula && <div className="mt-3 font-mono text-xs bg-white rounded-lg px-3 py-2 border border-black/5">{r.formula}</div>}
      </Card>
      <StatGrid obj={r.statistics} />
      <Flags flags={out.validation?.flags} />
      <div>
        <h3 className="font-serif text-xl mb-2">Assumptions</h3>
        <AssumptionTable checks={out.assumptions} />
      </div>
      {Object.entries(r.tables || {}).map(([name, rows]) =>
        Array.isArray(rows) && rows[0] && typeof rows[0] === "object" ? (
          <Card key={name} className="p-3 overflow-auto">
            <div className="text-xs uppercase tracking-wider text-ink/45 px-1 py-1">{name}</div>
            <table className="min-w-full text-xs">
              <thead>
                <tr>
                  {Object.keys(rows[0]).map((k) => (
                    <th key={k} className="text-left px-2 py-1 font-medium">
                      {k}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 40).map((row, i) => (
                  <tr key={i} className="border-t border-black/5">
                    {Object.keys(rows[0]).map((k) => (
                      <td key={k} className="px-2 py-1 font-mono">
                        {row[k] == null ? "—" : String(row[k]).slice(0, 48)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : null
      )}
      {out.chart && (
        <Card className="p-3">
          <Plot spec={out.chart} />
        </Card>
      )}
      {out.provenance && (
        <details className="text-xs text-ink/60">
          <summary>Analysis provenance record</summary>
          <pre className="mt-2 bg-white p-3 rounded-lg overflow-auto">{JSON.stringify(out.provenance, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
