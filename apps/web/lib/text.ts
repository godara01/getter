// Interview questions use fenced code blocks for snippets and logs.

export type Block = { kind: "text"; text: string } | { kind: "code"; lang: string; text: string };

export function splitBlocks(input: string): Block[] {
  const blocks: Block[] = [];
  const fence = /```([\w-]*)\n([\s\S]*?)```/g;
  let last = 0;
  for (const m of input.matchAll(fence)) {
    const before = input.slice(last, m.index).trim();
    if (before) blocks.push({ kind: "text", text: before });
    blocks.push({ kind: "code", lang: m[1], text: m[2].replace(/\n$/, "") });
    last = (m.index ?? 0) + m[0].length;
  }
  const rest = input.slice(last).trim();
  if (rest) blocks.push({ kind: "text", text: rest });
  return blocks;
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
