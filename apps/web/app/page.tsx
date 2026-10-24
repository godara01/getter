import Link from "next/link";
import { WaitlistForm } from "@/components/WaitlistForm";

const POINTS = [
  {
    title: "Like the real thing",
    body: "Questions on your own past work, design, debugging and incidents, with follow-ups that probe how deep your answers go.",
  },
  {
    title: "Honest feedback",
    body: "A score per skill against a published rubric, quoting your own words as evidence, so you can see exactly what to fix.",
  },
  {
    title: "A plan, not just a score",
    body: "Your top gaps come with practice tasks for this week. Take another interview and track your progress.",
  },
  {
    title: "Private by default",
    body: "Practice interviews are only ever visible to you. Delete any of them at any time.",
  },
];

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="space-y-5 pt-6">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Practice technical interviews. Get honest feedback.
        </h1>
        <p className="max-w-2xl text-lg text-muted">
          AI mock interviews for backend and DevOps/SRE engineers at junior to mid level. Find out
          where you stand before the interview that counts.
        </p>
        <Link
          href="/practice/"
          className="inline-block rounded-md bg-accent px-5 py-2.5 font-medium text-accent-fg"
        >
          Start a practice interview
        </Link>
      </section>
      <section className="grid gap-4 sm:grid-cols-2">
        {POINTS.map((p) => (
          <div key={p.title} className="rounded-lg border border-line bg-card p-5">
            <h2 className="font-medium">{p.title}</h2>
            <p className="mt-1 text-sm text-muted">{p.body}</p>
          </div>
        ))}
      </section>
      <WaitlistForm />
    </div>
  );
}
