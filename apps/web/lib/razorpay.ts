import type { CheckoutResult, Order } from "./api";

const SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

interface CheckoutOptions {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  prefill?: { email?: string };
  handler: (result: CheckoutResult) => void;
  modal: { ondismiss: () => void };
}

declare global {
  interface Window {
    Razorpay?: new (options: CheckoutOptions) => { open: () => void };
  }
}

/** Format paise or rupees as ₹1,199 for display. */
export function rupees(amountInr: number): string {
  return `₹${amountInr.toLocaleString("en-IN")}`;
}

/** Plural-aware label for a credit balance. */
export function creditsLabel(n: number): string {
  return n === 1 ? "1 paid interview" : `${n} paid interviews`;
}

function loadScript(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = SCRIPT;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error("Could not load the payment window."));
    document.body.appendChild(el);
  });
}

/** Opens Razorpay Checkout. Resolves with the signed result, or null if the window was closed. */
export async function openCheckout(order: Order, email?: string): Promise<CheckoutResult | null> {
  await loadScript();
  const Razorpay = window.Razorpay;
  if (!Razorpay) throw new Error("Could not load the payment window.");
  return new Promise((resolve) => {
    new Razorpay({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount_paise,
      currency: order.currency,
      name: "Getter",
      description: order.pack_title,
      prefill: email ? { email } : undefined,
      handler: (result) => resolve(result),
      modal: { ondismiss: () => resolve(null) },
    }).open();
  });
}
