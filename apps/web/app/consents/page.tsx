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
  async function download() {
    try {
      const data = await api.exportData();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "getter-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not download your data."); }
  }
  return <div className="space-y-4">
    <h1 className="text-2xl font-semibold">My consents</h1>
    <p><button onClick={download} className="underline">Download my data</button> (interviews, reports, consents and payments as a JSON file)</p>
    <p>Withdrawing records your choice. Delete interviews separately to erase their transcripts and reports.</p>
    <p role="alert">{error}</p>
    <ul>{items.map(item => <li key={item.id} className="border-b border-line py-3">
      {item.kind}: {item.text_version} · {item.granted ? "Accepted" : "Withdrawn"} · {new Date(item.updated_at).toLocaleString()}
      {item.granted && <button onClick={() => withdraw(item.id)} className="ml-3 underline">Withdraw</button>}
    </li>)}</ul>
  </div>;
}
