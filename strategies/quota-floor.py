__strategy__ = "quota-floor"
"""分区配额保底 · 已被实测否证，保留作为负结果证据 —— 不要用，不要在这个方向上继续加规则。

原假设：dev-reference 的 P0 已经 64/64、零罚分，但自造 30 夜场景 mine-s7 只完成 52/64、
R04 整区 0 块、`flexible_shortfall` 700 分，所以「平台排序不看分区配额」是可抢的分。

否证（见 submissions/LEDGER.md）：`choose_action` 全场只被问 50 次，缺口分区只在其中 **7 次**
出现在候选板上 —— `_finalize` 在没有可完成候选时直接 wait，根本不问策略。那 700 分源于
合法窗口稀缺，不是排序错。装上本策略后 mine-s7 **−1.77**、demo-week **+24.64**，
两场景完成块数与罚分**都没变**。而且 `terminal_penalty_avoidance`（FLEXIBLE 100）本来就已经
在平台给的 `estimated_total_gain` 里，按配额插队等于把同一笔钱算两遍。

保留的有用部分：`_consumed_fraction()` 用 `SAC_WALLCLOCK_SECONDS` + `time.monotonic()` 量出
墙钟消耗比例 —— 快照里没有总夜数，这是唯一可观测的预算信号，任何 LLM/重计算分支都要靠它降级。
"""

import os
import time

# Layer switches. Each one is meant to be attributable in submissions/LEDGER.md:
# flip one at a time and re-measure, never ship a bundle you cannot decompose.
ENABLE_QUOTA_FLOOR = True
ENABLE_WALLCLOCK_GUARD = True

# Fraction of the global wall clock after which we stop re-ordering for quota reasons and
# just take the platform's best estimate. Past this point there is no longer time to be
# picky, and a wasted slot costs a tile we can never come back for.
GUARD_FRACTION = 0.75

# A region only jumps the queue when it is this far below its quota. 1 is enough to make
# the deficit observable without reacting to a single tile that merely happened to be last.
MIN_DEFICIT = 1



def _budget_seconds():
    """The global wall clock for this run, or None if the environment does not say."""
    raw = os.environ.get("SAC_WALLCLOCK_SECONDS")
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _consumed_fraction(memory):
    """How much of the wall clock we have burnt, measured in our own process time.

    The snapshot never publishes the total night count, so remaining *nights* cannot be
    computed from it. Consumed budget is both observable and the actual cause of
    `global_wallclock_expired`, which makes it the right regime variable.
    """
    if not ENABLE_WALLCLOCK_GUARD:
        return 0.0
    budget = _budget_seconds()
    if budget is None:
        return 0.0
    started = memory.get("t0")
    if started is None:
        return 0.0
    return min(1.0, (time.monotonic() - started) / budget)


def _deficits(candidates, snapshot, config):
    """region_id -> tiles still owed, for regions we could act on right now."""
    quota = config.get("flexible_quota_per_region")
    if not isinstance(quota, int):
        return None  # rule generation without a quota; stay out of the way
    done = (snapshot.get("progress") or {}).get("flexible_completed_by_region") or {}
    regions = {c.get("region_id") for c in candidates if c.get("region_id")}
    return {r: max(0, quota - int(done.get(r, 0))) for r in regions}


def choose_action(candidates, snapshot, memory):
    if memory.get("t0") is None:
        memory["t0"] = time.monotonic()
    if not candidates:
        return None

    config = snapshot.get("score_config") or {}

    deficit = _deficits(candidates, snapshot, config) if ENABLE_QUOTA_FLOOR else None
    if not deficit:
        return candidates[0]

    # Late in the budget the floor stops applying: with no time left, the platform's
    # per-second estimate is a better decision than chasing an unreachable quota.
    if _consumed_fraction(memory) >= GUARD_FRACTION:
        return candidates[0]

    behind = {r for r, owed in deficit.items() if owed >= MIN_DEFICIT}
    if not behind:
        return candidates[0]

    # Among starved regions, take the platform's best candidate — not the first tile we
    # happen to find, so the ordering we do use is still the public scoring model's.
    for candidate in candidates:
        if candidate.get("region_id") in behind:
            candidate["reason"] = (
                f"quota-floor: {candidate['region_id']} owes {deficit[candidate['region_id']]} "
                f"of {config.get('flexible_quota_per_region')}"
            )[:240]
            return candidate
    return candidates[0]
