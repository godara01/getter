import { splitBlocks } from "@/lib/text";

export function RichText({ text }: { text: string }) {
  return (
    <div className="space-y-3">
      {splitBlocks(text).map((b, i) =>
        b.kind === "code" ? (
          <pre
            key={i}
            className="overflow-x-auto rounded-md border border-line bg-bg p-3 text-sm leading-relaxed"
          >
            <code>{b.text}</code>
          </pre>
        ) : (
          <p key={i} className="whitespace-pre-wrap leading-relaxed">
            {b.text}
          </p>
        ),
      )}
    </div>
  );
}
