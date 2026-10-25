"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorNote } from "@/components/ErrorNote";
import { track } from "@/lib/analytics";
import { ApiError, type Billing, api, getEmail } from "@/lib/api";
import { creditsLabel, openCheckout, rupees } from "@/lib/razorpay";

export default function Pricing() {
  const [billing, setBilling] = useState<Billing | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api.billing().then(setBilling, (err) =>
      setError(err instanceof ApiError ? err.message : "Could not load pricing."),
    );
  }, []);

  async function buy(packId: string) {
    setBusy(packId);
    setError(null);
    setNotice(null);
    try {
      const order = await api.createOrder(packId);
      const result = await openCheckout(order, getEmail() ?? undefined);
      if (!result) return;
      const confirmed = await api.verifyPayment(result);
      track("pack_purchased", { pack_id: packId });
      setBilling((b) => (b ? { ...b, credits: confirmed.credits } : b));
      setNotice("Payment received. Your paid interviews are ready.");
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "The payment did not complete. You have not been charged twice; try again.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Pricing</h1>
        <p className="mt-1 text-muted">
          Every account gets free practice interviews each day. Paid packs add more interviews for
          when you want to keep practising. Prices are in rupees and include no subscription.
        </p>
      </div>

      <ErrorNote message={error} />
      {notice && (
        <p role="status" className="rounded-md border border-line bg-card p-3 text-sm">
          {notice}{" "}
          <Link href="/practice/" className="font-medium text-accent underline">
            Start an interview
          </Link>
        </p>
      )}

      {billing && !billing.enabled && (
        <p className="rounded-md border border-line bg-card p-4 text-sm text-muted">
          Paid packs are not open yet. Free practice interviews work as usual.
        </p>
      )}

      {billing && (
        <>
          <p data-testid="balance" className="text-sm text-muted">
            Your balance: {creditsLabel(billing.credits)}. Paid interviews are used only after
            your free interviews for the day.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {billing.packs.map((p) => (
              <div key={p.id} className="rounded-lg border border-line bg-card p-5">
                <h2 className="font-medium">{p.title}</h2>
                <p className="mt-1 text-2xl font-semibold">{rupees(p.amount_inr)}</p>
                <p className="text-sm text-muted">
                  {rupees(Math.round((p.amount_inr / p.credits) * 10) / 10)} per interview
                </p>
                <button
                  type="button"
                  onClick={() => buy(p.id)}
                  disabled={!billing.enabled || busy !== null}
                  className="mt-4 rounded-md bg-accent px-4 py-2 font-medium text-accent-fg disabled:opacity-40"
                >
                  {busy === p.id ? "Opening payment…" : "Buy"}
                </button>
              </div>
            ))}
          </div>
        </>
      )}
      <p className="text-xs text-muted">
        Payments are handled by Razorpay (UPI, cards and netbanking). Getter never sees your card
        details. Read the <Link href="/terms/" className="underline">terms</Link> and{" "}
        <Link href="/privacy/" className="underline">privacy policy</Link>.
      </p>
    </div>
  );
}
