__strategy__ = "greedy"
"""官方默认基线 · P0 — trust the platform ranking blindly.

This is what `agent/minimal_agent.py` does with an untouched my_strategy.py: take
index 0 of the candidates, which the platform already sorted by
`estimated_gain_per_second`. Measured reference totals on the bundled scenarios are
recorded in docs/experiment-protocol.md; every strategy we write must beat this.
"""


def choose_action(candidates, snapshot, memory):
    if not candidates:
        return None
    return candidates[0]
