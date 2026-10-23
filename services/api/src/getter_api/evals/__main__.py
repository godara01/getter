from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from getter_api.evals import CASES_DIR, format_table, load_cases, run_eval
from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway


async def main() -> None:
    parser = argparse.ArgumentParser(description="Score grading models against expert grades.")
    parser.add_argument("cases", nargs="?", type=Path, default=CASES_DIR)
    parser.add_argument(
        "--config", action="append", default=[], help="LLM config YAML; repeat to compare"
    )
    args = parser.parse_args()
    cases = load_cases(args.cases)
    if any(c.synthetic for c in cases):
        print("Note: synthetic cases only test the harness; use expert-graded transcripts.\n")
    summaries = []
    for path in args.config or [None]:
        gateway = LLMGateway(load_llm_config(path))
        summaries.append(await run_eval(path or "dev", gateway, cases))
    print(format_table(summaries))
    for s in summaries:
        for r in s.results:
            if not r.ok:
                print(f"{s.label} failed on {r.case_id}: {r.error[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
