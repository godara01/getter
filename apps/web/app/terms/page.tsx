import Link from "next/link";

import { TERMS_VERSION } from "@/lib/legal";

export default function Terms() {
  return (
    <article className="space-y-4">
      <h1 className="text-2xl font-semibold">Terms of use (draft, pending legal review)</h1>
      <p className="rounded-md border border-line bg-card p-3 text-sm">
        Version: {TERMS_VERSION}. This is plain-language draft text, not yet reviewed by a lawyer.
        It will be reviewed before public launch, and you will be asked to accept the final version.
      </p>

      <h2 className="pt-2 text-lg font-medium">What Getter is</h2>
      <p>
        Getter runs AI practice interviews for backend and DevOps/SRE engineers and gives you
        written feedback. It is practice. A score or verdict is not a hiring decision, a
        certification or a promise of a job.
      </p>

      <h2 className="pt-2 text-lg font-medium">Your practice results are private</h2>
      <p>
        Your interviews, scores and reports are shown only to you. They are never shown to
        companies. If Getter later offers a certified assessment to companies, it will be a
        separate, opt-in step that asks for your consent first.
      </p>

      <h2 className="pt-2 text-lg font-medium">Feedback can be wrong</h2>
      <p>
        Scores come from AI models and quote your own words as evidence. They can be mistaken. Use
        them to find things to practise, and rate the report so we can improve it. In the practice
        terminal and code editor nothing you type is run against real systems, and code you run is
        executed in an isolated sandbox.
      </p>

      <h2 className="pt-2 text-lg font-medium">Using Getter fairly</h2>
      <p>
        Use your own account and answer for yourself. Do not try to break the service, probe other
        people&apos;s data, or copy and publish the interview questions in bulk.
      </p>

      <h2 className="pt-2 text-lg font-medium">Free interviews and paid packs</h2>
      <p>
        Every account gets a limited number of free interviews each day. You can buy packs of extra
        interviews on the <Link href="/pricing/" className="underline">pricing page</Link>.
        Payments are processed by Razorpay; Getter does not see or store your card details. Paid
        interviews do not expire in this draft. If an interview fails because of a fault on our
        side and you get no report, write to us and we will add the interview back to your balance.
        Refund rules for unused packs will be set in the final terms.
      </p>

      <h2 className="pt-2 text-lg font-medium">Deleting your data and leaving</h2>
      <p>
        You can delete any interview yourself, withdraw consents on{" "}
        <Link href="/consents/" className="underline">My consents</Link>, and download your data
        there. Withdrawing a consent records your choice; it does not erase interviews, so delete
        those separately. To close your account and erase your practice data, write to us (see the{" "}
        <Link href="/privacy/" className="underline">privacy policy</Link>).
      </p>

      <h2 className="pt-2 text-lg font-medium">Changes</h2>
      <p>
        When these terms change we publish a new version and ask you to accept it before your next
        interview.
      </p>
    </article>
  );
}
