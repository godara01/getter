"""A scripted terminal for DevOps scenarios. Nothing the candidate types is executed.

Each scenario lists rules in YAML: a regex for the whole command and the text to print.
Flags make the scenario stateful (after `ufw allow 443/tcp` the connection test works).
State is not stored: it is rebuilt by replaying the candidate's earlier commands for the
question, so the transcript stays the single source of truth.

A short pipe chain such as `ss -tlnp | grep 443` is handled by running the first command
through the rules and applying simple filters (grep, head, tail, wc -l) to its output.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from getter_api.content import TerminalTask

MAX_COMMAND_CHARS = 200

# Programs a real box would have. Without a scripted rule they print a neutral note, so a
# plausible command is not mistaken for a typo.
COMMON_COMMANDS = frozenset(
    [
        *[
            "awk",
            "cat",
            "cd",
            "chmod",
            "chown",
            "cp",
            "crontab",
            "curl",
            "cut",
            "date",
            "df",
            "dig",
            "dmesg",
            "docker",
            "du",
            "echo",
            "env",
        ],
        *[
            "find",
            "free",
            "grep",
            "head",
            "history",
            "hostname",
            "id",
            "ip",
            "iptables",
            "journalctl",
            "kill",
            "kubectl",
            "less",
            "ls",
        ],
        *[
            "lsof",
            "mount",
            "nc",
            "netstat",
            "nft",
            "nginx",
            "nslookup",
            "ping",
            "ps",
            "pwd",
            "rm",
            "sed",
            "sort",
            "ss",
            "ssh",
            "stat",
            "sudo",
        ],
        *[
            "systemctl",
            "tail",
            "tar",
            "top",
            "touch",
            "traceroute",
            "uname",
            "uniq",
            "uptime",
            "vi",
            "vim",
            "wc",
            "which",
            "whoami",
        ],
        "ufw",
    ]
)

HELP = (
    "This is a simulated terminal for practice. Nothing runs for real: only commands "
    "that matter for this scenario print output. Type the commands you would run, one at "
    "a time, then explain your reasoning in your answer."
)


@dataclass
class TerminalReply:
    output: str
    flags: frozenset[str]


class CommandRejected(ValueError):
    """The text is not something to run (empty, too long or several lines)."""


def normalize(command: str) -> str:
    if "\n" in command or "\r" in command:
        raise CommandRejected("enter one command at a time")
    command = " ".join(command.split())
    if not command:
        raise CommandRejected("enter a command")
    if len(command) > MAX_COMMAND_CHARS:
        raise CommandRejected(f"commands are limited to {MAX_COMMAND_CHARS} characters")
    return command


def _strip_sudo(command: str) -> str:
    while command == "sudo" or command.startswith("sudo "):
        command = command[5:].lstrip()
        # Skip sudo's own simple flags, like `sudo -n`.
        while command.startswith("-") and " " in command:
            command = command.split(" ", 1)[1]
    return command


def _split_pipes(command: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote = ""
    for ch in command:
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "|":
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    parts.append("".join(current).strip())
    return parts


def _run_rules(task: TerminalTask, flags: frozenset[str], command: str) -> TerminalReply | None:
    for rule in task.rules:
        if not re.fullmatch(rule.pattern, command):
            continue
        if any(f not in flags for f in rule.requires) or any(f in flags for f in rule.unless):
            continue
        return TerminalReply(rule.output.rstrip("\n"), flags | frozenset(rule.sets))
    return None


def _first_word(command: str) -> str:
    return command.split(" ", 1)[0]


def _base_reply(task: TerminalTask, flags: frozenset[str], command: str) -> TerminalReply:
    command = _strip_sudo(command)
    if _first_word(command) in ("help", "man"):
        return TerminalReply(HELP, flags)
    reply = _run_rules(task, flags, command)
    if reply is not None:
        return reply
    name = _first_word(command)
    if name in COMMON_COMMANDS or name in task.extra_commands:
        return TerminalReply(f"(no output: `{name}` has nothing scripted for this command)", flags)
    return TerminalReply(f"bash: {name}: command not found", flags)


def _filter(output: str, stage: str) -> str:
    try:
        argv = shlex.split(stage)
    except ValueError:
        return f"bash: syntax error in `{stage}`"
    if not argv:
        return "bash: syntax error near unexpected token `|'"
    lines = output.splitlines()
    name, args = argv[0], argv[1:]
    if name in ("grep", "egrep"):
        flags_ = {a for a in args if a.startswith("-")}
        words = [a for a in args if not a.startswith("-")]
        if not words:
            return "Usage: grep [OPTION]... PATTERN"
        extended = name == "egrep" or "-E" in flags_
        text = words[0] if extended else re.escape(words[0])
        try:
            rx = re.compile(text, re.IGNORECASE if "-i" in flags_ else 0)
        except re.error:
            return f"grep: invalid regular expression `{words[0]}`"
        invert = "-v" in flags_
        return "\n".join(line for line in lines if bool(rx.search(line)) != invert)
    if name in ("head", "tail"):
        count = 10
        for i, arg in enumerate(args):
            if arg == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
                count = int(args[i + 1])
            elif arg.startswith("-") and arg[1:].isdigit():
                count = int(arg[1:])
        chosen = lines[:count] if name == "head" else lines[-count:] if count else []
        return "\n".join(chosen)
    if name == "wc" and args == ["-l"]:
        return str(len(lines))
    return f"(simulated terminal: `{name}` is not supported after a pipe; run steps one at a time)"


def respond(task: TerminalTask, flags: frozenset[str], command: str) -> TerminalReply:
    """Output for one command and the flags after it. The command is normalised first."""
    command = normalize(command)
    stages = _split_pipes(command)
    if any(not s for s in stages):
        return TerminalReply("bash: syntax error near unexpected token `|'", flags)
    reply = _base_reply(task, flags, stages[0])
    output = reply.output
    for stage in stages[1:]:
        output = _filter(output, stage)
    return TerminalReply(output, reply.flags)


def replay(task: TerminalTask, history: list[str]) -> frozenset[str]:
    """Scenario flags after the earlier commands for this question."""
    flags: frozenset[str] = frozenset()
    for command in history:
        try:
            flags = respond(task, flags, command).flags
        except CommandRejected:
            continue
    return flags
