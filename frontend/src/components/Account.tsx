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
          <div className="glass-inset p-3">
            <p className="mb-1">Klistra in koden i tilläggets popup. Den visas bara nu.</p>
            <code className="block break-all font-mono text-xs">{token}</code>
            <button className="mt-2 text-xs font-semibold text-neon-cyan hover:underline" onClick={() => navigator.clipboard.writeText(token)}>Kopiera</button>
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
        <select className="field !w-auto"
          value={platform} onChange={(e) => setPlatform(e.target.value)}>
          <option value="console">Konsol</option>
          <option value="pc">PC</option>
        </select>
        <button disabled={busy}
          className="btn-primary !w-auto !rounded-xl !py-2 px-4 !text-sm"
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
