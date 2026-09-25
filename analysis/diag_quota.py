__strategy__ = "diag-quota"
"""诊断：配额保底到底有没有机会开火。记录计数，不做决策（等价 greedy）。"""

import collections
import json
import sys

TARGET = ("R03", "R04")


def choose_action(candidates, snapshot, memory):
    st = memory.setdefault("st", {
        "n": 0, "with_target": 0, "picked_target": 0,
        "target_best_rank": collections.Counter(), "deficit_hist": collections.Counter(),
        "no_target_reason": collections.Counter(), "quota_missing": 0,
    })
    st["n"] += 1
    quota = (snapshot.get("score_config") or {}).get("flexible_quota_per_region")
    if quota is None:
        st["quota_missing"] += 1
    done = (snapshot.get("progress") or {}).get("flexible_completed_by_region") or {}

    regs = {c.get("region_id") for c in candidates}
    hit = [t for t in TARGET if t in regs]
    if hit:
        st["with_target"] += 1
    else:
        # Is the starved region absent from candidates, or already satisfied?
        for t in TARGET:
            owed = quota - int(done.get(t, 0)) if isinstance(quota, int) else None
            st["no_target_reason"][f"{t}:owed={owed}"] += 1
    st["deficit_hist"][tuple(sorted(done.get(t, 0) for t in TARGET))] += 1

    best = candidates[0] if candidates else None
    if best is not None:
        if best.get("region_id") in TARGET:
            st["picked_target"] += 1
        else:
            idx = next((i for i, c in enumerate(candidates) if c.get("region_id") in TARGET), None)
            st["target_best_rank"][idx if idx is None else min(idx, 30)] += 1

    if st["n"] % 10 == 0 or st["n"] <= 2:
        print("[diag] " + json.dumps({
            "n": st["n"], "with_target": st["with_target"], "picked_target": st["picked_target"],
            "quota": quota, "done": {k: done.get(k, 0) for k in TARGET},
            "ncand": len(candidates), "regions_in_cands": sorted(regs),
            "target_rank_when_not_best": dict(st["target_best_rank"]),
            "no_target_reason": dict(st["no_target_reason"]),
        }, ensure_ascii=False), file=sys.stderr, flush=True)
    return best
