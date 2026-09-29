const TOKEN_KEY = "methodica_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

async function req(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body && !(opts.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
    opts = { ...opts, body: JSON.stringify(opts.body) };
  }
  const res = await fetch(path, { ...opts, headers });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { message: text };
  }
  if (!res.ok) {
    const err = new Error(data?.message || data?.detail || `Request failed (${res.status})`);
    err.payload = data;
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  login: (email, password) => req("/api/auth/login", { method: "POST", body: { email, password } }),
  register: (payload) => req("/api/auth/register", { method: "POST", body: payload }),
  me: () => req("/api/auth/me"),
  dashboard: () => req("/api/dashboard"),
  projects: () => req("/api/projects"),
  createProject: (body) => req("/api/projects", { method: "POST", body }),
  datasets: (projectId) => req("/api/datasets" + (projectId ? `?project_id=${projectId}` : "")),
  dataset: (id) => req(`/api/datasets/${id}`),
  deleteDataset: (id) => req(`/api/datasets/${id}`, { method: "DELETE" }),
  upload: (files, projectId) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    if (projectId) fd.append("project_id", projectId);
    return req("/api/datasets/upload", { method: "POST", body: fd });
  },
  sample: (which, projectId) =>
    req(`/api/datasets/sample/${which}` + (projectId ? `?project_id=${projectId}` : ""), { method: "POST" }),
  preview: (id, offset = 0, limit = 80) => req(`/api/datasets/${id}/preview?offset=${offset}&limit=${limit}`),
  profile: (id) => req(`/api/datasets/${id}/profile`),
  quality: (id) => req(`/api/datasets/${id}/quality`),
  history: (id) => req(`/api/datasets/${id}/history`),
  clean: (id, operations) => req(`/api/datasets/${id}/clean`, { method: "POST", body: { operations } }),
  undo: (id) => req(`/api/datasets/${id}/undo`, { method: "POST", body: {} }),
  restore: (id, version) => req(`/api/datasets/${id}/restore`, { method: "POST", body: { version } }),
  explore: (id, body = {}) => req(`/api/datasets/${id}/explore`, { method: "POST", body }),
  group: (id, body) => req(`/api/datasets/${id}/group`, { method: "POST", body }),
  chart: (id, body) => req(`/api/datasets/${id}/chart`, { method: "POST", body }),
  methods: () => req("/api/methods"),
  recommend: (id, body) => req(`/api/datasets/${id}/recommend`, { method: "POST", body }),
  assumptions: (id, body) => req(`/api/datasets/${id}/assumptions`, { method: "POST", body }),
  analyze: (id, body) => req(`/api/datasets/${id}/analyze`, { method: "POST", body }),
  analyses: (datasetId) => req("/api/analyses" + (datasetId ? `?dataset_id=${datasetId}` : "")),
  analysis: (id) => req(`/api/analyses/${id}`),
  reproduce: (id) => req(`/api/analyses/${id}/reproduce`, { method: "POST", body: {} }),
  autopilot: (id, body) => req(`/api/datasets/${id}/autopilot`, { method: "POST", body }),
  assistant: (id, body) => req(`/api/datasets/${id}/assistant`, { method: "POST", body }),
  report: (id, body) => req(`/api/datasets/${id}/report`, { method: "POST", body }),
  reports: () => req("/api/reports"),
  fromSql: (body) => req("/api/datasets/from-sql", { method: "POST", body }),
};
