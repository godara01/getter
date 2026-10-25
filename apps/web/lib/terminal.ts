import type { Session, Turn } from "./api";

type Terminal = NonNullable<Session["terminal"]>;

export interface Exchange {
  command: string;
  output: string;
}

/** Commands and outputs for the terminal question on screen, oldest first. */
export function scrollback(turns: Turn[], terminal: Terminal): Exchange[] {
  const out: Exchange[] = [];
  for (const t of turns) {
    if (t.question_id !== terminal.question_id) continue;
    if (t.kind === "command") out.push({ command: t.text, output: "" });
    else if (t.kind === "command_output" && out.length > 0) out[out.length - 1].output = t.text;
  }
  return out;
}

export function commandsLeft(terminal: Pick<Terminal, "max_commands" | "commands_used">): number {
  return Math.max(0, terminal.max_commands - terminal.commands_used);
}

/** The prompt shown before each command, like a shell's. */
export function promptLabel(terminal: Pick<Terminal, "user" | "hostname">): string {
  return `${terminal.user}@${terminal.hostname}:~$`;
}

/** Up/down arrow recall. `position` counts back from the newest command (0 = none). */
export function recall(
  history: string[],
  position: number,
  direction: "up" | "down",
): { position: number; text: string } {
  const next =
    direction === "up" ? Math.min(history.length, position + 1) : Math.max(0, position - 1);
  return { position: next, text: next === 0 ? "" : history[history.length - next] };
}

/** Whether a turn belongs to the live terminal and is shown there, not in the transcript. */
export function inLiveTerminal(turn: Turn, terminal: Terminal | null): boolean {
  return (
    terminal !== null &&
    turn.question_id === terminal.question_id &&
    (turn.kind === "command" || turn.kind === "command_output")
  );
}
