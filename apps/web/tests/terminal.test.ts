import { describe, expect, it } from "vitest";

import type { Turn } from "../lib/api";
import { commandsLeft, inLiveTerminal, promptLabel, recall, scrollback } from "../lib/terminal";

const terminal = {
  question_id: "port_443",
  hostname: "web-01",
  user: "ops",
  welcome: "",
  max_commands: 5,
  commands_used: 2,
};

function turn(index: number, kind: Turn["kind"], text: string, question_id = "port_443"): Turn {
  return {
    index,
    speaker: kind === "command" ? "candidate" : "interviewer",
    kind,
    section_id: "linux",
    question_id,
    text,
    created_at: "2026-10-25T10:00:00Z",
  };
}

describe("scrollback", () => {
  it("pairs commands with their output for the live question only", () => {
    const turns = [
      turn(0, "question", "A web server stopped…"),
      turn(1, "command", "ss -tlnp"),
      turn(2, "command_output", "LISTEN"),
      turn(3, "command", "ufw status", "other_question"),
      turn(4, "command_output", "Status: active", "other_question"),
      turn(5, "command", "iptables -S"),
    ];
    expect(scrollback(turns, terminal)).toEqual([
      { command: "ss -tlnp", output: "LISTEN" },
      { command: "iptables -S", output: "" },
    ]);
  });
});

describe("helpers", () => {
  it("counts commands left and never goes below zero", () => {
    expect(commandsLeft(terminal)).toBe(3);
    expect(commandsLeft({ ...terminal, commands_used: 9 })).toBe(0);
  });

  it("formats the prompt", () => {
    expect(promptLabel(terminal)).toBe("ops@web-01:~$");
  });

  it("recalls earlier commands with the arrow keys", () => {
    const history = ["a", "b", "c"];
    let r = recall(history, 0, "up");
    expect(r).toEqual({ position: 1, text: "c" });
    r = recall(history, r.position, "up");
    expect(r.text).toBe("b");
    r = recall(history, 3, "up");
    expect(r).toEqual({ position: 3, text: "a" });
    expect(recall(history, 1, "down")).toEqual({ position: 0, text: "" });
    expect(recall([], 0, "up")).toEqual({ position: 0, text: "" });
  });

  it("hides terminal turns from the transcript only while the terminal is live", () => {
    expect(inLiveTerminal(turn(1, "command", "ls"), terminal)).toBe(true);
    expect(inLiveTerminal(turn(1, "command", "ls", "x"), terminal)).toBe(false);
    expect(inLiveTerminal(turn(1, "answer", "text"), terminal)).toBe(false);
    expect(inLiveTerminal(turn(1, "command", "ls"), null)).toBe(false);
  });
});
