import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state.jsx";
import { Btn, Card, ErrorBox, Field, NeedDataset, PageTitle, Plot, Select } from "../components.jsx";

export default function Explore() {
  const { datasetId, profile } = useApp();
  const [eda, setEda] = useState(null);
  const [err, setErr] = useState(null);
  const [kind, setKind] = useState("histogram");
  const [x, setX] = useState("");
  const [y, setY] = useState("");
  const [chart, setChart] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    api.explore(datasetId).then(setEda).catch(setErr);
  }, [datasetId]);

  const cols = profile?.columns?.map((c) => c.name) || [];

  return (
    <NeedDataset>
      <PageTitle
        kicker="Explore"
        title="Exploratory analysis"
        subtitle="Distributions, correlations, and charts generated from the working dataset — not from a language model."
      />
      <ErrorBox err={err} />
      {eda && (
        <>
          <Card className="p-4 mb-4 overflow-auto">
            <h2 className="font-serif text-xl mb-3">Descriptive statistics</h2>
            <table className="min-w-full text-xs">
              <thead>
                <tr className="text-left text-ink/50">
                  {["name", "n", "mean", "median", "std", "min", "max", "skewness", "missing_pct"].map((h) => (
                    <th key={h} className="px-2 py-1 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(eda.descriptives || []).map((r) => (
                  <tr key={r.name} className="border-t border-black/5">
                    {["name", "n", "mean", "median", "std", "min", "max", "skewness", "missing_pct"].map((h) => (
                      <td key={h} className="px-2 py-1 font-mono">
                        {r[h] == null ? "—" : typeof r[h] === "number" ? Number(r[h]).toPrecision(4) : String(r[h])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card className="p-4 mb-4">
            <h2 className="font-serif text-xl mb-3">Build a chart</h2>
            <div className="grid md:grid-cols-4 gap-3 mb-3">
              <Field label="Type">
                <Select
                  value={kind}
                  onChange={setKind}
                  options={["histogram", "box", "violin", "scatter", "line", "heatmap", "qq", "bar"]}
                />
              </Field>
              <Field label="X">
                <Select value={x} onChange={setX} options={cols} placeholder="—" />
              </Field>
              <Field label="Y">
                <Select value={y} onChange={setY} options={cols} placeholder="—" />
              </Field>
              <div className="flex items-end">
                <Btn
                  onClick={async () => {
                    try {
                      const c = await api.chart(datasetId, { kind, x, y, column: y || x });
                      setChart(c);
                    } catch (e) {
                      setErr(e);
                    }
                  }}
                >
                  Draw
                </Btn>
              </div>
            </div>
            <Plot spec={chart} />
          </Card>
          <div className="grid md:grid-cols-2 gap-4">
            {(eda.charts || []).map((c, i) => (
              <Card key={i} className="p-3">
                <Plot spec={c} height={320} />
              </Card>
            ))}
          </div>
        </>
      )}
    </NeedDataset>
  );
}
