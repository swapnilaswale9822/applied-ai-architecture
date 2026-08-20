#!/usr/bin/env python3
"""CI entry point.

    python ci_gate.py goldens.json

Exit codes are the contract:

    0  every blocking gate met
    1  a blocking gate failed — do not release
    2  the harness itself is misconfigured (e.g. no adversarial cases)

Code 2 is the one people leave out, and it is the one that matters. Without it, a suite that
silently stopped running its adversarial cases reports the same green as one that ran them
and passed — so the gate degrades to decoration without anyone noticing.
"""

import sys

from harness import GoldenSet, evaluate
from harness.gates import MISCONFIGURED


def demo_agent(text: str):
    """Placeholder. Replace with an HTTP call to the agent under test."""
    return {"text": f"echo: {text}", "citations": [], "retrieved_sources": []}


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: ci_gate.py <golden-set.json>", file=sys.stderr)
        return MISCONFIGURED
    try:
        with open(argv[1]) as fh:
            golden_set = GoldenSet.from_json(fh.read())
    except (OSError, ValueError) as exc:
        print(f"could not load golden set: {exc}", file=sys.stderr)
        return MISCONFIGURED

    result = evaluate(demo_agent, golden_set)
    print(result.summary())
    for case in result.failed_cases():
        for failure in case.failures():
            print(f"  {case.golden_id} [{case.scenario_class}] "
                  f"{failure['assertion']}: {failure['detail']}")
    return result.verdict.exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
