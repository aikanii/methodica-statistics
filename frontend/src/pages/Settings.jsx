import React from "react";
import { useApp } from "../state.jsx";
import { Card, PageTitle } from "../components.jsx";

export default function Settings() {
  const { user } = useApp();
  return (
    <div>
      <PageTitle kicker="Settings" title="Workspace preferences" subtitle="No account required. Data stays on this local server." />
      <div className="grid md:grid-cols-2 gap-4">
        <Card className="p-5">
          <h2 className="font-serif text-xl mb-2">Account</h2>
          <dl className="text-sm space-y-1">
            <div>
              <dt className="text-ink/45 text-xs uppercase tracking-wider">Name</dt>
              <dd>{user?.name}</dd>
            </div>
            <div>
              <dt className="text-ink/45 text-xs uppercase tracking-wider">Email</dt>
              <dd>{user?.email}</dd>
            </div>
            <div>
              <dt className="text-ink/45 text-xs uppercase tracking-wider">Role</dt>
              <dd>{user?.role}</dd>
            </div>
          </dl>
        </Card>
        <Card className="p-5">
          <h2 className="font-serif text-xl mb-2">Privacy & integrity</h2>
          <ul className="text-sm space-y-2 text-ink/70">
            <li>This is a local workspace — no sign-in is required.</li>
            <li>The assistant never invents statistical results or citations.</li>
            <li>Cleaning is opt-in. Provenance records dataset version, method, and parameters.</li>
            <li>Uploaded files are not shared with third-party services.</li>
          </ul>
        </Card>
        <Card className="p-5 md:col-span-2">
          <h2 className="font-serif text-xl mb-2">Statistical engine</h2>
          <p className="text-sm text-ink/70">
            Computations use pandas, NumPy, SciPy, statsmodels, scikit-learn, pingouin, and lifelines. Established
            algorithms are not reimplemented. Methodica {`1.0.0`} · Python FastAPI backend.
          </p>
        </Card>
      </div>
    </div>
  );
}
