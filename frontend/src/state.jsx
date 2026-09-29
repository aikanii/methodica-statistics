import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "./api";

const Ctx = createContext(null);
export const useApp = () => useContext(Ctx);

export function AppState({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [datasetId, setDatasetId] = useState(localStorage.getItem("methodica_ds") || null);
  const [dataset, setDataset] = useState(null);
  const [profile, setProfile] = useState(null);
  const [lastAnalysis, setLastAnalysis] = useState(null);

  useEffect(() => {
    api
      .me()
      .then((u) => {
        setUser(u);
      })
      .catch(() => {
        setUser({ id: "guest", email: "guest@methodica.app", name: "You", role: "analyst" });
      })
      .finally(() => setBooting(false));
  }, []);

  useEffect(() => {
    if (datasetId) localStorage.setItem("methodica_ds", datasetId);
    else localStorage.removeItem("methodica_ds");
  }, [datasetId]);

  async function selectDataset(id) {
    setDatasetId(id);
    if (!id) {
      setDataset(null);
      setProfile(null);
      return;
    }
    const [d, p] = await Promise.all([api.dataset(id), api.profile(id)]);
    setDataset(d);
    setProfile(p);
  }

  useEffect(() => {
    if (user && datasetId && !dataset) {
      selectDataset(datasetId).catch(() => setDatasetId(null));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const value = useMemo(
    () => ({
      user,
      setUser,
      booting,
      datasetId,
      dataset,
      profile,
      setProfile,
      lastAnalysis,
      setLastAnalysis,
      selectDataset,
      logout() {
        setToken(null);
        setUser(null);
        setDataset(null);
        setDatasetId(null);
      },
    }),
    [user, booting, datasetId, dataset, profile, lastAnalysis]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
