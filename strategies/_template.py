__strategy__ = "template"
"""策略骨架 · Strategy template — 复制它开新策略，或者 `python scripts/ao.py new <name> --promote`.

平台每次决策把「此刻合法可拍的候选」按 `estimated_gain_per_second` 排好序交给你，
index 0 就是每秒收益最高的那块。你的全部工作就是：换一个候选、或者这一时隙等待。

Only stdlib. Only the data already inside `candidates` / `snapshot` / `memory`.
Never read scenario files, never import anything outside agent/, never print to stdout.
"""


def choose_action(candidates, snapshot, memory):
    """Return a candidate dict (you may set candidate["reason"]), an int index, a tile_id str, or None to wait.

    Anything illegal or raised falls back to the platform's default ranking, logged in agent.log.
    """
    if not candidates:
        return None

    # memory is a plain dict, created once per run — the only thing that persists between decisions.
    stats = memory.setdefault("stats", {"observed": 0, "waited": 0})

    best = candidates[0]

    # Put your overrides here. Keep them justified by a measured number, not by intuition:
    # two of the rules in reference.py are disabled with `if False` because they lose score.
    stats["observed"] += 1
    best["reason"] = f"{__strategy__}: {best['tile_id']}"
    return best
