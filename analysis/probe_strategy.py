__strategy__ = "probe3"
"""临时探针 3：effective_weather 是否含 instrument_efficiency；weekly 覆盖几晚；v3 独有字段。"""

import json
import sys


def dump(label, value):
    print(f"[probe3] {label}: {json.dumps(value, ensure_ascii=False, default=str)[:1200]}", file=sys.stderr, flush=True)


def choose_action(candidates, snapshot, memory):
    seen = memory.setdefault("seen", {})
    memory["n"] = memory.get("n", 0) + 1

    if not seen.get("weather"):
        seen["weather"] = True
        dump("schema_version", snapshot.get("schema_version"))
        dump("snapshot keys (all)", sorted(snapshot))
        ct = (snapshot.get("candidate_tiles") or [{}])[0]
        dump("effective_weather", ct.get("effective_weather"))
        dump("effective_weather keys", sorted(ct.get("effective_weather") or {}))
        dump("geometry keys", sorted(ct.get("geometry") or {}))
        dump("current_site_weather keys", sorted(snapshot.get("current_site_weather") or {}))
        dump("v3-only: tile_last_finished", snapshot.get("tile_last_finished"))
        dump("v3-only: fault_status", snapshot.get("fault_status"))

    wk = snapshot.get("weekly")
    if wk and not seen.get("weekly_span"):
        seen["weekly_span"] = True
        tws = wk.get("tile_windows") or []
        dump("weekly.tile_windows count", len(tws))
        dump("weekly distinct night_id", sorted({w.get("night_id") for w in tws}))
        dump("weekly issued_at vs cursor", [wk.get("issued_at_utc"), snapshot["cursor"]["timestamp_utc"]])
    ns = snapshot.get("night_start")
    if ns and not seen.get("night_span"):
        seen["night_span"] = True
        dump("night_start distinct night_id", sorted({w.get("night_id") for w in ns.get("tile_windows") or []}))

    if memory["n"] == 250:
        dump("nights seen so far", sorted({s.get("night_id") for s in [snapshot["cursor"]]}))
        dump("cursor at decision 250", snapshot["cursor"])
    return candidates[0] if candidates else None
