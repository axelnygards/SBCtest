import { useState } from "react";

import { api, setToken, type Me } from "../lib/api";

export function Account({ me, onChange }: { me: Me | null; onChange: () => void }) {
  const [token, setShownToken] = useState<string | null>(null);
  const [platform, setPlatform] = useState("console");
  const [busy, setBusy] = useState(false);

  if (me)
    return (
      <div className="space-y-2 text-sm">
        <p>
          Klubb: <b>{me.club_size}</b> spelare
          {me.club_imported_at ? ` · importerad ${new Date(me.club_imported_at + "Z").toLocaleString("sv-SE")}` : " · inte importerad än"}
        </p>
        {token && (
          <div className="rounded-md bg-slate-100 p-2 dark:bg-slate-800">
            <p className="mb-1">Klistra in koden i tilläggets popup. Den visas bara nu.</p>
            <code className="block break-all font-mono text-xs">{token}</code>
            <button className="mt-1 text-blue-600 hover:underline" onClick={() => navigator.clipboard.writeText(token)}>Kopiera</button>
          </div>
        )}
        <button className="text-xs text-slate-500 hover:underline" onClick={() => { setToken(null); onChange(); }}>
          Logga ut på den här enheten
        </button>
      </div>
    );

  return (
    <div className="space-y-2 text-sm">
      <p>
        Skapa ett anonymt konto för att använda din egen klubb. Du anger aldrig EA-inloggning här: klubben
        importeras med webbläsartillägget.
      </p>
      <div className="flex gap-2">
        <select className="rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          value={platform} onChange={(e) => setPlatform(e.target.value)}>
          <option value="console">Konsol</option>
          <option value="pc">PC</option>
        </select>
        <button disabled={busy}
          className="rounded-md bg-blue-600 px-3 py-1 font-medium text-white disabled:opacity-50"
          onClick={async () => {
            setBusy(true);
            try {
              const u = await api.createUser(platform);
              setToken(u.token!);
              setShownToken(u.token!);
              onChange();
            } finally {
              setBusy(false);
            }
          }}>
          Skapa konto & kopplingskod
        </button>
      </div>
    </div>
  );
}
