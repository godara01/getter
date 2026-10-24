"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type Consent } from "@/lib/api";

export default function Consents() {
  const [items, setItems] = useState<Consent[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { api.consents().then(setItems).catch(e => setError(e instanceof ApiError ? e.message : "Could not load consents.")); }, []);
  async function withdraw(id: string) {
    try {
      await api.withdrawConsent(id);
      setItems(await api.consents());
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not withdraw consent."); }
  }
  return <div className="space-y-4">
    <h1 className="text-2xl font-semibold">My consents</h1>
    <p>Withdrawing records your choice. Delete interviews separately to erase their transcripts and reports.</p>
    <p role="alert">{error}</p>
    <ul>{items.map(item => <li key={item.id} className="border-b border-line py-3">
      {item.kind}: {item.text_version} · {item.granted ? "Accepted" : "Withdrawn"} · {new Date(item.updated_at).toLocaleString()}
      {item.granted && <button onClick={() => withdraw(item.id)} className="ml-3 underline">Withdraw</button>}
    </li>)}</ul>
  </div>;
}
