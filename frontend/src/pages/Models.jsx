import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state.jsx";
import { Btn, Card, ErrorBox, Field, NeedDataset, PageTitle, Select } from "../components.jsx";
import { ResultPane } from "./Analyze.jsx";

const GROUPS = [
  {
    title: "Regression",
    items: [
      ["linear_regression", "Simple / multiple linear"],
      ["polynomial_regression", "Polynomial"],
      ["logistic_regression", "Logistic"],
      ["poisson_regression", "Poisson"],
      ["negative_binomial", "Negative binomial"],
      ["robust_regression", "Robust (HC3)"],
    ],
  },
  {
    title: "Time series",
    items: [
      ["trend_analysis", "Linear trend"],
      ["moving_average", "Moving average"],
      ["acf_pacf", "ACF / PACF"],
      ["arima", "ARIMA"],
      ["sarima", "SARIMA"],
      ["exp_smoothing", "Exponential smoothing"],
      ["seasonality", "Seasonal profile"],
    ],
  },
  {
    title: "Multivariate",
    items: [
      ["pca", "PCA"],
      ["factor_analysis", "Factor analysis"],
      ["kmeans", "K-means"],
      ["lda", "Discriminant analysis"],
      ["manova", "MANOVA"],
    ],
  },
  {
    title: "Survival & reliability",
    items: [
      ["kaplan_meier", "Kaplan–Meier"],
      ["logrank", "Log-rank"],
      ["cox_ph", "Cox PH"],
      ["cronbach_alpha", "Cronbach's α"],
    ],
  },
];

export default function Models() {
  const { datasetId, profile, setLastAnalysis } = useApp();
  const [method, setMethod] = useState("linear_regression");
  const [y, setY] = useState("");
  const [x, setX] = useState("");
  const [x2, setX2] = useState("");
  const [duration, setDuration] = useState("");
  const [event, setEvent] = useState("");
  const [err, setErr] = useState(null);
  const [out, setOut] = useState(null);
  const [busy, setBusy] = useState(false);
  const cols = profile?.columns?.map((c) => c.name) || [];
  const nums = (profile?.columns || []).filter((c) => c.role === "numeric").map((c) => c.name);

  async function run() {
    setBusy(true);
    setErr(null);
    const params = { y, x: x2 ? [x, x2].filter(Boolean) : x, duration, event, columns: nums };
    try {
      const res = await api.analyze(datasetId, { method, params });
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
        kicker="Models"
        title="Direct access"
        subtitle="Advanced users can fit models without the recommender. Assumptions and validation still run."
      />
      <ErrorBox err={err} />
      <div className="grid md:grid-cols-4 gap-3 mb-5">
        {GROUPS.map((g) => (
          <Card key={g.title} className="p-3">
            <div className="text-[11px] uppercase tracking-wider text-ink/45 mb-2">{g.title}</div>
            <div className="space-y-1">
              {g.items.map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setMethod(id)}
                  className={`block w-full text-left text-sm px-2 py-1 rounded ${
                    method === id ? "bg-pine text-white" : "hover:bg-white"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </Card>
        ))}
      </div>
      <Card className="p-4 mb-5">
        <div className="grid md:grid-cols-4 gap-3">
          <Field label="Outcome / series">
            <Select value={y} onChange={setY} options={cols} placeholder="y" />
          </Field>
          <Field label="Predictor / group">
            <Select value={x} onChange={setX} options={cols} placeholder="x" />
          </Field>
          <Field label="Second predictor">
            <Select value={x2} onChange={setX2} options={cols} placeholder="optional" />
          </Field>
          <Field label="Duration / event (survival)">
            <div className="grid grid-cols-2 gap-2">
              <Select value={duration} onChange={setDuration} options={cols} placeholder="time" />
              <Select value={event} onChange={setEvent} options={cols} placeholder="event" />
            </div>
          </Field>
        </div>
        <Btn className="mt-4" onClick={run} disabled={busy}>
          Fit {method.replaceAll("_", " ")}
        </Btn>
      </Card>
      {out && <ResultPane out={out} />}
    </NeedDataset>
  );
}
