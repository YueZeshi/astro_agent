#!/usr/bin/env python3
"""astro_agent workspace driver · 本地运行 / 评分 / 对比 / 打包.

Subcommands: run · score · select · new · sweep · pack · results

The official starter kit lives in harness/ and is read-only. Everything here only
calls into it; our code is agent/ (the submittable unit) and strategies/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
AGENT_DIR = ROOT / "agent"
STRATEGY_DIR = ROOT / "strategies"
SCENARIO_DIR = HARNESS / "scenarios"
RUNS_DIR = ROOT / "runs"

ENTRY = AGENT_DIR / "minimal_agent.py"
ACTIVE = AGENT_DIR / "my_strategy.py"
SCORER = HARNESS / "score_decisions.py"
RUNNER = HARNESS / "local_runner.py"

DEFAULT_WALLCLOCK = {"dev-reference": 600, "demo-week": 900, "finals-preview": 900}


def _die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _scenario_path(name: str) -> Path:
    path = (SCENARIO_DIR / name).resolve()
    if not path.is_dir():
        available = ", ".join(sorted(p.name for p in SCENARIO_DIR.iterdir() if p.is_dir()))
        _die(f"unknown scenario '{name}' (expected harness/scenarios/{name}). Bundled: {available}")
    return path


def _wallclock(name: str, override):
    if override:
        return float(override)
    manifest = SCENARIO_DIR / name / "outputs" / "reference" / "scenario_manifest.json"
    if manifest.exists():
        try:
            value = json.loads(manifest.read_text(encoding="utf-8")).get("global_wallclock_seconds")
            if value:
                return float(value)
        except (ValueError, OSError):
            pass
    return float(DEFAULT_WALLCLOCK.get(name, 600))


def _strategy_file(name: str) -> Path:
    path = Path(name)
    if not path.suffix:
        path = STRATEGY_DIR / f"{name}.py"
    if not path.is_absolute():
        path = (ROOT / path) if not path.exists() else path
    if not path.is_file():
        _die(f"no strategy file for '{name}' (looked at {path})")
    return path


def _strategy_name(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:40]:
        if line.startswith("__strategy__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return path.stem


def _run_py(args, cwd=ROOT) -> int:
    return subprocess.run([sys.executable, *args], cwd=str(cwd)).returncode


def _score_report(run_dir: Path) -> dict:
    path = run_dir / "score_report.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(report: dict) -> dict:
    score = report.get("score", {})
    return {
        "total": score.get("total"),
        "base_science": score.get("base_science"),
        "program_bonus": score.get("program_bonus"),
        "request_reward": score.get("request_reward"),
        "coverage_bonus": score.get("coverage_bonus"),
        "penalties": sum((score.get("penalties") or {}).values()),
        "termination": report.get("termination_reason"),
        "tiles": len((report.get("completion") or {}).get("completed_tiles") or []),
    }


def _write_meta(run_dir: Path, meta: dict) -> None:
    meta["written_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


# --- commands ------------------------------------------------------------------------------------

def cmd_run(args) -> int:
    scenario = args.scenario
    spath = _scenario_path(scenario)
    if args.strategy:
        _promote(_strategy_file(args.strategy))
    if not ACTIVE.exists():
        _die("agent/my_strategy.py is missing — run `python scripts/ao.py select baseline` first")

    run_dir = (ROOT / args.out).resolve() if args.out else RUNS_DIR / _default_run_id(scenario, args.tag)
    run_dir.mkdir(parents=True, exist_ok=True)

    wallclock = _wallclock(scenario, args.wallclock)
    cmd = [str(RUNNER), "--scenario", str(spath), "--agent", str(ENTRY),
           "--wallclock", str(wallclock), "--out", str(run_dir)]
    if args.quiet:
        cmd.append("--quiet")
    print("+ " + " ".join(cmd))
    code = _run_py(cmd)

    report = _score_report(run_dir)
    if report:
        s = _summary(report)
        print(f"\n{run_dir.name}: total={s['total']} science={s['base_science']} "
              f"bonus={s['program_bonus']} requests={s['request_reward']} penalties={-s['penalties']} "
              f"tiles={s['tiles']} -> {s['termination']}")
        _write_meta(run_dir, {
            "scenario": scenario, "strategy": _strategy_name(ACTIVE),
            "strategy_path": str(ACTIVE.relative_to(ROOT)),
            "wallclock_seconds": wallclock, "runner_exit": code,
            "summary": s, "runner_args": cmd,
            "strategy_sha256": _sha(ACTIVE),
        })
    else:
        print(f"\nrunner exited {code} with no score_report.json — see {run_dir / 'agent.log'}")
    return code


def _default_run_id(scenario: str, tag: str | None) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    strategy = _strategy_name(ACTIVE) if ACTIVE.exists() else "unknown"
    parts = [stamp, scenario, strategy] + ([tag] if tag else [])
    return "-".join(p.replace("_", "-") for p in parts)


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _promote(src: Path) -> None:
    shutil.copyfile(src, ACTIVE)
    print(f"promoted {src.relative_to(ROOT)} -> {ACTIVE.relative_to(ROOT)} (strategy '{_strategy_name(src)}')")


def cmd_select(args) -> int:
    _promote(_strategy_file(args.strategy))
    return 0


def cmd_new(args) -> int:
    target = STRATEGY_DIR / f"{args.name}.py"
    if target.exists():
        _die(f"{target} already exists")
    source = _strategy_file(args.from_strategy) if args.from_strategy else STRATEGY_DIR / "_template.py"
    body = source.read_text(encoding="utf-8") if source.exists() else (ACTIVE.read_text(encoding="utf-8"))
    body = body.replace("__strategy__ = \"", f"__strategy__ = \"{args.name}-copy-of-", 1) \
        if "__strategy__" in body else f'__strategy__ = "{args.name}"\n\n' + body
    target.write_text(body, encoding="utf-8")
    print(f"created {target.relative_to(ROOT)}")
    if args.promote:
        _promote(target)
    return 0


def cmd_score(args) -> int:
    if args.run:
        run_dir = (ROOT / args.run).resolve()
        report = _score_report(run_dir)
        if not report and not (run_dir / "decisions.csv").exists():
            _die(f"{run_dir} has no decisions.csv")
        decisions = run_dir / "decisions.csv"
        scenario = args.scenario or (json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))["scenario"]
                                    if (run_dir / "meta.json").exists() else None)
        if not scenario:
            _die("pass --scenario (meta.json missing)")
        args.decisions, args.scenario = str(decisions), scenario
    elif not args.decisions or not args.scenario:
        _die("pass either --run <dir> or both --decisions and --scenario")
    cmd = [str(SCORER), "--scenario", str(_scenario_path(args.scenario)), "--decisions", str(args.decisions)]
    if getattr(args, "out", None):
        cmd += ["--out", str(args.out)]
    return _run_py(cmd)


def cmd_sweep(args) -> int:
    strategies = args.strategies.split(",")
    scenarios = args.scenarios.split(",")
    rows = []
    for strat in strategies:
        path = _strategy_file(strat)
        for scenario in scenarios:
            for rep in range(args.repeats):
                _promote(path)
                run_args = argparse.Namespace(scenario=scenario, strategy=None, wallclock=args.wallclock,
                                              tag=f"sweep{rep if args.repeats > 1 else ''}", quiet=True,
                                              out=None)
                run_dir = ROOT / "runs" / _default_run_id(scenario, run_args.tag)
                run_args.out = str(run_dir.relative_to(ROOT))
                code = cmd_run(run_args)
                s = _summary(_score_report(run_dir))
                s.update(strategy=_strategy_name(path), scenario=scenario, rep=rep, exit=code,
                         run=run_dir.name)
                rows.append(s)
                print(f"  -> {scenario} {strat} rep{rep}: total={s['total']}")
    _print_table(rows, ("strategy", "scenario", "rep", "total", "base_science", "program_bonus",
                        "request_reward", "penalties", "tiles", "termination"))
    (ROOT / "runs" / "sweep-latest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


def cmd_results(args) -> int:
    rows = []
    for meta in sorted(RUNS_DIR.glob("*/meta.json")):
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        s = m.get("summary", {})
        rows.append({"strategy": m.get("strategy"), "scenario": m.get("scenario"), **s,
                     "dir": meta.parent.name})
    if not rows:
        print("no runs recorded yet — try `python scripts/ao.py run --scenario dev-reference`")
        return 0
    rows.sort(key=lambda r: (r.get("total") is None, -(r.get("total") or 0)))
    _print_table(rows, ("strategy", "scenario", "total", "base_science", "program_bonus",
                        "request_reward", "penalties", "tiles", "termination", "dir"))
    return 0


def cmd_pack(args) -> int:
    out = args.out or str(ROOT / "runs" / "agent.zip")
    return _run_py([str(HARNESS / "pack_agent.py"), "--agent", str(AGENT_DIR), "--out", out]
                   + (["--no-env"] if args.no_env else []))


def _print_table(rows, cols) -> None:
    if not rows:
        return
    widths = {c: max(len(c), *(len(_fmt(r.get(c))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(_fmt(r.get(c)).ljust(widths[c]) for c in cols))


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:,.2f}"
    return "" if v is None else str(v)


# --- argparse ------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ao", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the active agent on a scenario and score it")
    r.add_argument("--scenario", default="dev-reference")
    r.add_argument("--strategy", help="promote this strategy first (name in strategies/ or a path)")
    r.add_argument("--wallclock", help="override the scenario's global wallclock seconds")
    r.add_argument("--out", help="run directory (default: runs/<utc>-<scenario>-<strategy>)")
    r.add_argument("--tag", help="extra suffix on the auto run id")
    r.add_argument("--quiet", action="store_true")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("select", help="copy a strategy into agent/my_strategy.py")
    s.add_argument("strategy")
    s.set_defaults(func=cmd_select)

    n = sub.add_parser("new", help="scaffold a new strategy in strategies/")
    n.add_argument("name")
    n.add_argument("--from-strategy", dest="from_strategy", help="start from an existing strategy")
    n.add_argument("--promote", action="store_true", help="also make it the active strategy")
    n.set_defaults(func=cmd_new)

    c = sub.add_parser("score", help="independently recompute a decisions.csv score")
    c.add_argument("--run", help="run directory, e.g. runs/20260925-dev-reference-baseline")
    c.add_argument("--decisions")
    c.add_argument("--scenario")
    c.add_argument("--out")
    c.set_defaults(func=cmd_score)

    w = sub.add_parser("sweep", help="run several strategies across scenarios and print a table")
    w.add_argument("--strategies", required=True, help="comma-separated strategy names")
    w.add_argument("--scenarios", default="dev-reference")
    w.add_argument("--repeats", type=int, default=1)
    w.add_argument("--wallclock")
    w.set_defaults(func=cmd_sweep)

    b = sub.add_parser("results", help="table of recorded runs, best first")
    b.set_defaults(func=cmd_results)

    k = sub.add_parser("pack", help="zip agent/ for an agent submission")
    k.add_argument("--out")
    k.add_argument("--no-env", dest="no_env", action="store_true")
    k.set_defaults(func=cmd_pack)
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    raise SystemExit(a.func(a))
