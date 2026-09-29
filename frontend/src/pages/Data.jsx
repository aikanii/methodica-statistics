import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state.jsx";
import {
  AssumptionTable,
  Btn,
  Card,
  DataTable,
  ErrorBox,
  Field,
  Input,
  PageTitle,
  StatusPill,
} from "../components.jsx";

const TABS = ["Upload", "Preview", "Quality", "Cleaning", "History"];

export default function Data() {
  const { dataset, datasetId, selectDataset, profile, setProfile, setLastAnalysis } = useApp();
  const [tab, setTab] = useState("Upload");
  const [list, setList] = useState([]);
  const [preview, setPreview] = useState(null);
  const [quality, setQuality] = useState(null);
  const [history, setHistory] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [sql, setSql] = useState({ url: "sqlite:///storage/methodica.db", query: "", name: "SQL extract" });

  async function refreshList() {
    const rows = await api.datasets();
    setList(rows);
  }
  useEffect(() => {
    refreshList().catch(() => {});
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    if (tab === "Preview") api.preview(datasetId).then(setPreview).catch(setErr);
    if (tab === "Quality") api.quality(datasetId).then(setQuality).catch(setErr);
    if (tab === "History") api.history(datasetId).then(setHistory).catch(setErr);
    if (tab === "Cleaning" && !quality) api.quality(datasetId).then(setQuality).catch(() => {});
  }, [tab, datasetId]);

  async function onFiles(files) {
    setBusy(true);
    setErr(null);
    try {
      const res = await api.upload(files);
      await selectDataset(res.id);
      await refreshList();
      setTab("Preview");
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  async function removeDataset(id) {
    const target = list.find((d) => d.id === id);
    const label = target?.name || "this dataset";
    if (!window.confirm(`Remove “${label}”? Files, analyses, and reports for it will be deleted. This cannot be undone.`)) {
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await api.deleteDataset(id);
      if (datasetId === id) {
        setPreview(null);
        setQuality(null);
        setHistory(null);
        setLastAnalysis(null);
        const remaining = list.filter((d) => d.id !== id);
        if (remaining[0]) await selectDataset(remaining[0].id);
        else await selectDataset(null);
      }
      await refreshList();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  async function loadSample(which) {
    setBusy(true);
    setErr(null);
    try {
      const res = await api.sample(which);
      await selectDataset(res.id);
      await refreshList();
      setTab("Preview");
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageTitle
        kicker="Data"
        title="Datasets"
        subtitle="Import, profile, and clean. Proposed fixes are never applied until you accept them."
        actions={
          datasetId ? (
            <Btn variant="danger" disabled={busy} onClick={() => removeDataset(datasetId)}>
              Remove dataset
            </Btn>
          ) : null
        }
      />
      <ErrorBox err={err} />
      <div className="flex gap-6">
        <div className="w-56 shrink-0">
          <div className="text-[11px] uppercase tracking-wider text-ink/45 mb-2">Your tables</div>
          <ul className="space-y-1">
            {list.map((d) => (
              <li key={d.id} className={`rounded-lg ${datasetId === d.id ? "bg-pine text-white" : "hover:bg-white"}`}>
                <div className="flex items-start gap-1">
                  <button
                    onClick={() => selectDataset(d.id)}
                    className="flex-1 min-w-0 text-left px-3 py-2 text-sm"
                  >
                    <div className="truncate font-medium">{d.name}</div>
                    <div className={`text-[11px] ${datasetId === d.id ? "text-white/70" : "text-ink/45"}`}>
                      {d.n_rows} × {d.n_cols}
                    </div>
                  </button>
                  <button
                    title="Remove dataset"
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      removeDataset(d.id);
                    }}
                    className={`shrink-0 mt-1.5 mr-1.5 px-1.5 py-0.5 rounded text-[11px] ${
                      datasetId === d.id ? "text-white/80 hover:bg-white/15" : "text-ink/40 hover:text-red-800 hover:bg-red-50"
                    }`}
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex gap-1 mb-4 border-b border-black/10">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-2 text-sm ${tab === t ? "border-b-2 border-pine text-pine font-medium" : "text-ink/55"}`}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === "Upload" && (
            <div className="space-y-4">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDrag(false);
                  if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files);
                }}
                className={`rounded-2xl border-2 border-dashed p-10 text-center ${
                  drag ? "border-pine bg-mist" : "border-black/15 bg-cream"
                }`}
              >
                <div className="font-serif text-2xl">Drop CSV, Excel, JSON, Parquet, or SQLite</div>
                <p className="text-sm text-ink/55 mt-2">Multiple files are concatenated. Nothing is sent to a third party.</p>
                <label className="inline-block mt-4">
                  <input
                    type="file"
                    multiple
                    className="hidden"
                    onChange={(e) => e.target.files?.length && onFiles(e.target.files)}
                  />
                  <span className="px-3.5 py-2 rounded-lg text-sm font-medium bg-pine text-white cursor-pointer">
                    {busy ? "Uploading…" : "Choose files"}
                  </span>
                </label>
              </div>
              <div className="grid md:grid-cols-3 gap-3">
                {[
                  ["air", "Air quality", "PM2.5 urban / rural with injected quality issues"],
                  ["clinical", "Clinical trial", "Treatment, scores, survival time & event"],
                  ["survey", "Survey items", "Likert items for reliability / Cronbach"],
                ].map(([id, t, d]) => (
                  <Card key={id} className="p-4">
                    <div className="font-medium">{t}</div>
                    <p className="text-xs text-ink/55 mt-1 mb-3">{d}</p>
                    <Btn variant="ghost" onClick={() => loadSample(id)} disabled={busy}>
                      Load sample
                    </Btn>
                  </Card>
                ))}
              </div>
              <Card className="p-4">
                <div className="font-medium mb-2">SQL import</div>
                <div className="grid md:grid-cols-2 gap-3">
                  <Field label="Connection URL">
                    <Input value={sql.url} onChange={(e) => setSql({ ...sql, url: e.target.value })} />
                  </Field>
                  <Field label="Name">
                    <Input value={sql.name} onChange={(e) => setSql({ ...sql, name: e.target.value })} />
                  </Field>
                  <div className="md:col-span-2">
                    <Field label="Query">
                      <textarea
                        value={sql.query}
                        onChange={(e) => setSql({ ...sql, query: e.target.value })}
                        className="w-full bg-white border border-black/10 rounded-lg px-3 py-2 text-sm font-mono h-20"
                        placeholder="SELECT * FROM my_table LIMIT 5000"
                      />
                    </Field>
                  </div>
                </div>
                <Btn
                  className="mt-3"
                  variant="ghost"
                  onClick={async () => {
                    setBusy(true);
                    try {
                      const res = await api.fromSql(sql);
                      await selectDataset(res.id);
                      await refreshList();
                    } catch (e) {
                      setErr(e);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Import from SQL
                </Btn>
              </Card>
            </div>
          )}

          {tab === "Preview" && dataset && (
            <div>
              {profile && <SummaryStrip profile={profile} dataset={dataset} />}
              <Card className="p-3 mt-4">
                <DataTable columns={preview?.columns} rows={preview?.rows} />
                <div className="text-xs text-ink/45 mt-2 px-1">
                  Showing {preview?.rows?.length || 0} of {preview?.n_rows} rows
                </div>
              </Card>
            </div>
          )}

          {tab === "Quality" && quality && (
            <div className="space-y-4">
              <div className="flex items-end gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-ink/45">Quality score</div>
                  <div className="font-serif text-5xl text-pine">{quality.score}</div>
                </div>
                <div className="text-sm text-ink/60 mb-2">
                  {quality.counts?.high} high · {quality.counts?.medium} medium · {quality.counts?.low} low
                </div>
              </div>
              <p className="text-sm italic text-ink/70">The system proposes these changes. Nothing has been modified.</p>
              <div className="space-y-2">
                {(quality.issues || []).map((iss, i) => (
                  <Card key={i} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <StatusPill status={iss.severity} />
                          <span className="font-medium text-sm">{iss.problem}</span>
                        </div>
                        <p className="text-sm text-ink/65 mt-1">{iss.explanation}</p>
                        <p className="text-sm mt-1">
                          <span className="text-ink/45">Suggestion · </span>
                          {iss.suggestion}
                        </p>
                      </div>
                      {iss.proposed && datasetId && (
                        <Btn
                          variant="ghost"
                          onClick={async () => {
                            await api.clean(datasetId, [iss.proposed]);
                            const [p, q] = await Promise.all([api.profile(datasetId), api.quality(datasetId)]);
                            setProfile(p);
                            setQuality(q);
                            await selectDataset(datasetId);
                          }}
                        >
                          Accept
                        </Btn>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {tab === "Cleaning" && (
            <CleaningPanel
              datasetId={datasetId}
              quality={quality}
              onDone={async () => {
                await selectDataset(datasetId);
                const q = await api.quality(datasetId);
                setQuality(q);
              }}
            />
          )}

          {tab === "History" && history && (
            <div className="space-y-3">
              <div className="text-sm text-ink/60">Current version v{history.current}. Every operation is reversible.</div>
              {(history.versions || []).map((v) => (
                <Card key={v.version} className="p-3 flex items-center justify-between">
                  <div>
                    <div className="font-medium text-sm">v{v.version}</div>
                    <div className="text-xs text-ink/50">{v.note}</div>
                  </div>
                  {v.version !== history.current && (
                    <Btn variant="ghost" onClick={() => api.restore(datasetId, v.version).then(() => selectDataset(datasetId))}>
                      Restore
                    </Btn>
                  )}
                </Card>
              ))}
              <Btn variant="ghost" onClick={() => api.undo(datasetId).then(() => selectDataset(datasetId))}>
                Undo last
              </Btn>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryStrip({ profile, dataset }) {
  const items = [
    ["Rows", profile.n_rows],
    ["Columns", profile.n_cols],
    ["Memory", profile.memory],
    ["Missing", profile.missing_pct + "%"],
    ["Duplicates", profile.duplicate_rows],
    ["Quality", profile.quality_score],
  ];
  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
      {items.map(([k, v]) => (
        <div key={k} className="rounded-xl bg-cream border border-black/5 px-3 py-2">
          <div className="text-[10px] uppercase tracking-wider text-ink/45">{k}</div>
          <div className="font-serif text-xl">{v}</div>
        </div>
      ))}
    </div>
  );
}

function CleaningPanel({ datasetId, quality, onDone }) {
  const [col, setCol] = useState("");
  const [method, setMethod] = useState("median");
  if (!datasetId) return <p className="text-sm text-ink/60">Load a dataset first.</p>;
  const cols = quality ? [] : [];
  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="font-medium mb-3">Apply operations</div>
        <div className="flex flex-wrap gap-2">
          <Btn variant="ghost" onClick={() => api.clean(datasetId, [{ operation: "drop_duplicates" }]).then(onDone)}>
            Remove duplicate rows
          </Btn>
          <Btn variant="ghost" onClick={() => api.clean(datasetId, [{ operation: "impute_all", method: "auto" }]).then(onDone)}>
            Auto-impute missing
          </Btn>
          {quality?.proposals?.length > 0 && (
            <Btn
              onClick={() =>
                api.clean(datasetId, quality.proposals).then(onDone)
              }
            >
              Apply all proposals
            </Btn>
          )}
        </div>
        <div className="grid md:grid-cols-3 gap-3 mt-4">
          <Field label="Column">
            <Input value={col} onChange={(e) => setCol(e.target.value)} placeholder="column name" />
          </Field>
          <Field label="Impute method">
            <select
              className="w-full bg-white border border-black/10 rounded-lg px-3 py-2 text-sm"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
            >
              {["mean", "median", "mode", "ffill", "bfill", "interpolate", "knn", "iterative"].map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </Field>
          <div className="flex items-end">
            <Btn
              variant="ghost"
              onClick={() => api.clean(datasetId, [{ operation: "impute", column: col, method }]).then(onDone)}
            >
              Impute column
            </Btn>
          </div>
        </div>
      </Card>
      <p className="text-xs text-ink/50">
        Also available via the engine: winsorize, clip negatives, one-hot encode, z-score, log transform, date parse.
        Use Autopilot or the assistant if you prefer not to pick operations by name.
      </p>
    </div>
  );
}
