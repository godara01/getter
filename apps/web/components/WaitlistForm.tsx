"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";

export function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("backend");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      setMessage((await api.waitlist(email, role)).message);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "Could not join. Please try again.");
    } finally { setBusy(false); }
  }
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Follow what comes next</h2>
      <p>Join the waitlist for practice updates. We store your email and role interest; this form sends no email.</p>
      <form onSubmit={submit} className="flex flex-wrap gap-3">
        <label>Email <input type="email" required maxLength={320} value={email} onChange={e => setEmail(e.target.value)} className="rounded border border-line bg-card p-2" /></label>
        <label>Role interest <select value={role} onChange={e => setRole(e.target.value)} className="rounded border border-line bg-card p-2">
          <option value="backend">Backend engineer</option>
          <option value="devops_sre">DevOps / SRE engineer</option>
          <option value="other">Other</option>
        </select></label>
        <button disabled={busy} className="rounded bg-accent px-4 py-2 text-accent-fg">Join waitlist</button>
      </form>
      <p role="status">{message}</p>
    </section>
  );
}
