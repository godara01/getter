import Link from "next/link";

import { TERMS_VERSION, contactText } from "@/lib/legal";

const STORED = [
  ["Account", "Your email address and, if you sign in with Clerk, the account id Clerk gives us."],
  [
    "Interviews",
    "Your answers, the commands and code you submit, the interviewer's questions, and the timing of each section.",
  ],
  [
    "Reports",
    "Scores per skill with the quotes used as evidence, the summary, strengths, your learning plan, and your usefulness rating and comment.",
  ],
  ["Consents", "Which terms version you accepted or withdrew, and when."],
  [
    "Payments",
    "The pack you bought, the amount, and Razorpay's order and payment ids. Card or UPI details stay with Razorpay.",
  ],
  [
    "Technical records",
    "Which AI model handled each call, its cost and delay (not your text), an audit log of who viewed or changed your data, and error reports without answer text.",
  ],
  ["Waitlist", "Your email and the role you are interested in, if you joined the waitlist."],
];

export default function Privacy() {
  return (
    <article className="space-y-4">
      <h1 className="text-2xl font-semibold">Privacy policy (draft, pending legal review)</h1>
      <p className="rounded-md border border-line bg-card p-3 text-sm">
        Version: {TERMS_VERSION}. Plain-language draft written to follow India&apos;s Digital
        Personal Data Protection Act. A lawyer will review it before public launch.
      </p>

      <h2 className="pt-2 text-lg font-medium">Short version</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>Your practice interviews and reports are private to you. Companies never see them.</li>
        <li>We do not sell your data or use it for advertising.</li>
        <li>You can download your data and delete your interviews at any time.</li>
        <li>We do not try to read emotions, personality or accents. Feedback is about the technical content.</li>
      </ul>

      <h2 className="pt-2 text-lg font-medium">What we store</h2>
      <dl className="space-y-2">
        {STORED.map(([name, text]) => (
          <div key={name}>
            <dt className="font-medium">{name}</dt>
            <dd className="text-muted">{text}</dd>
          </div>
        ))}
      </dl>

      <h2 className="pt-2 text-lg font-medium">Why, and who else handles it</h2>
      <p>
        We use your answers to run the interview, grade it and show you feedback. To do that,
        your answers are sent to the AI model providers we use, which can change as we compare
        models. We ask providers not to train on this data where they offer that option. Other
        services that handle data for us: Clerk (sign-in), Razorpay (payments), our hosting and
        database providers, and optionally Resend (email), Sentry (error reports) and PostHog
        (anonymous usage counts). Analytics and error reports never include answer text, and you
        can switch analytics off with the opt-out link at the bottom of the page.
      </p>

      <h2 className="pt-2 text-lg font-medium">How long we keep it</h2>
      <p>
        Interviews and reports stay until you delete them or close your account. Payment records are
        kept as long as tax and accounting rules require, even after you close your account.
      </p>

      <h2 className="pt-2 text-lg font-medium">Your choices</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <strong>See and download:</strong> use &quot;Download my data&quot; on{" "}
          <Link href="/consents/" className="underline">My consents</Link>.
        </li>
        <li>
          <strong>Delete interviews:</strong> delete any interview from{" "}
          <Link href="/sessions/" className="underline">My interviews</Link>.
        </li>
        <li>
          <strong>Withdraw consent:</strong> on My consents. You will need to accept the terms
          again to start another interview.
        </li>
        <li>
          <strong>Close your account and erase everything:</strong> write to {contactText()}.
          We erase your interviews, reports, consents and waitlist entry and keep only an
          anonymous account record and payment records.
        </li>
        <li>
          <strong>Correct or complain:</strong> write to the same address. You can also complain to
          the Data Protection Board of India.
        </li>
      </ul>

      <h2 className="pt-2 text-lg font-medium">Children</h2>
      <p>Getter is for adults. Do not use it if you are under 18.</p>
    </article>
  );
}
