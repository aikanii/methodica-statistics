import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api";
import { useApp } from "../state.jsx";
import { Btn, ErrorBox, Input } from "../components.jsx";

export default function Login() {
  const { setUser } = useApp();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("demo@methodica.app");
  const [password, setPassword] = useState("demo1234");
  const [name, setName] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = mode === "login" ? await api.login(email, password) : await api.register({ email, password, name });
      setToken(res.token);
      setUser(res.user);
      nav("/");
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid md:grid-cols-2">
      <div className="hidden md:flex flex-col justify-between bg-ink text-cream p-12">
        <div>
          <div className="font-serif text-4xl">Methodica</div>
          <div className="uppercase tracking-[0.22em] text-xs text-white/40 mt-2">evidence you can inspect</div>
        </div>
        <div className="max-w-md">
          <p className="font-serif text-3xl leading-snug">
            Data → evidence → method → assumptions → calculation → validation → interpretation.
          </p>
          <p className="text-white/60 mt-6 text-sm leading-relaxed">
            A statistical workbench that chooses tests for you, shows why, and refuses to invent a p-value. Built for
            students, researchers, and analysts who need defensible results — not a black box.
          </p>
        </div>
        <div className="text-xs text-white/35">Local-first demo · datasets never leave this session’s workspace</div>
      </div>
      <div className="grid place-items-center p-8 bg-paper">
        <form onSubmit={submit} className="w-full max-w-sm">
          <h1 className="font-serif text-3xl mb-1">{mode === "login" ? "Sign in" : "Create account"}</h1>
          <p className="text-sm text-ink/60 mb-6">Use the demo account or register your own.</p>
          {mode === "register" && (
            <div className="mb-3">
              <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
          )}
          <div className="mb-3">
            <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="mb-4">
            <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <ErrorBox err={err} />
          <Btn type="submit" disabled={busy} className="w-full mt-3">
            {busy ? "Working…" : mode === "login" ? "Enter workspace" : "Register"}
          </Btn>
          <button
            type="button"
            className="mt-4 text-sm text-pine underline"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "Need an account?" : "Already registered?"}
          </button>
          <div className="mt-8 rounded-xl bg-mist/80 p-3 text-xs text-ink/70">
            Demo · <span className="font-mono">demo@methodica.app</span> / <span className="font-mono">demo1234</span>
          </div>
        </form>
      </div>
    </div>
  );
}
