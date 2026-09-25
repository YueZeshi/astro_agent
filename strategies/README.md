# strategies/

一份策略 = 一个自包含的 `.py` 文件，导出 `choose_action(candidates, snapshot, memory)`。

Development happens here. Submission does not: the unit that ships is `agent/my_strategy.py`.
Promote a file from this directory into `agent/` and it becomes what every run uses:

```
python scripts/ao.py select coverage-aware     # promote
python scripts/ao.py run --scenario dev-reference
python scripts/ao.py run --strategy coverage-aware --scenario dev-reference   # both at once
```

`ao.py run` writes `runs/<id>/meta.json` recording the promoted strategy's `__strategy__` name and
the file's SHA-256, so a run directory always says which strategy produced it.

## Conventions

- First line is `__strategy__ = "<name>"`. That string is what appears in `meta.json` and `ao.py results`.
- One self-contained file per strategy — no imports from this repo. Anything shared has to be copied
  in, because `pack_agent.py` only ships `agent/` and the platform has no `strategies/` directory.
- stdlib only, unless you also edit `agent/requirements.txt` and accept the LLM path.
- Do not read `harness/scenarios/**` from inside a strategy. The agent process is sandboxed to
  `agent/`; a strategy that peeks at `weather.csv` truth is a rules violation, not an optimisation.

## 当前阶梯

| name | 来源 | demo-week 实测 | 备注 |
|---|---|---|---|
| `greedy` | 官方未改动的默认 | **5,909.099093** | P0。取 `candidates[0]`；dev-reference 上 **12,287.478365** |
| `reference` | `agent/reference_strategy.py` 原样 | **5,909.099093** | 组织方的「完整示范」—— 与 P0 **逐位相同**，实测确认它在这两代练习场景上只能打平 |
| `_template` | 本项目 | — | `ao.py new` 的起点，不是对手 |

`reference` 打平不是意外：它的两条覆盖类规则在练习场景上是空转（`coverage_bonus_weight` 缺省为 0），
而它的「等天况」分支被 `if False` 关掉（官方实测那条 **−1,700**）。
**所以真正的对手不是它，是隐藏场景。** 余量分析见
[docs/strategy-design.md](../docs/strategy-design.md)。

分数来源：`python scripts/ao.py results`（读 `runs/*/meta.json`）。
