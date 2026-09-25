# 提交台账 · Submission ledger

一行一次**有结论的**运行。平台额度（dev-reference 显示上限 10 次/天）是真实预算，
所以只提交在本地已经跑赢当前最佳、且在自造场景上同向的结果。

分数来源：`python scripts/ao.py results`（读 `runs/*/meta.json`）。

| # | 日期 (UTC) | 策略 | 场景 | 墙钟 | total | base_science | program_bonus | request_reward | 罚分 | vs P0 | 结论 | 产物 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-09-25 | `greedy` (P0) | dev-reference | 7200 | **12,287.478365** | 7,178.82 | 1,188.66 | 3,920.00 | 0.00 | — | 官方 reference 锚点，逐位一致 | `runs/20260925-050134-dev-reference-greedy-p0/` |
| 0 | 2026-09-25 | `greedy` (P0) | demo-week | 900 | **5,909.099093** | 5,228.32 | 900.78 | 280.00 | 500.00 | — | 快速回归门（20 s） | `runs/20260925-051318-demo-week-greedy-p0/` |
| 1 | 2026-09-25 | `reference` | demo-week | 900 | **5,909.099093** | 5,228.32 | 900.78 | 280.00 | 500.00 | **±0.00** | 官方「完整示范」与 P0 **逐位相同** —— 练习场景上覆盖类规则空转、等天况分支被 `if False` 关掉。它不是对手 | `runs/20260925-051939-demo-week-reference-verify/` |
| 0 | 2026-09-25 | `greedy` (P0) | `mine-s7`（自造 30 夜） | 7200 | **4,483.429216** | 4,545.85 | 497.58 | 140.00 | 700.00 | — | 第二个锚点。**52/64 块、`flexible_shortfall` 700** —— 见下 | `runs/20260925-053830-mine-s7-greedy-gen/` |

| 2 | 2026-09-25 | `quota-floor` | mine-s7 | 7200 | 4,481.655320 | 4,545.10 | 496.56 | 140.00 | 700.00 | **−1.77** | **否证 A6**：块数仍 52、罚分仍 700 | 产物已清理，命令见下 |
| 2 | 2026-09-25 | `quota-floor` | demo-week | 900 | 5,933.742968 | 5,252.60 | 901.15 | 280.00 | 500.00 | **+24.64** | 同上：罚分与块数不变，涨的是被换天区的科学分 —— **不是配额生效的证据** | 产物已清理 |

## 关键实测：每场只有 ~50–91 次真实决策（推翻了本台账前一版的判断）

`decisions.csv` 里绝大多数行**不是策略的选择**，而是 `agent/decision_graph.py:_finalize`
在没有可完成候选时直接返回的 wait（reason =
`no legal observable candidate can finish in its known window`，**不调用 `choose_action`**）：

| 场景 | 时隙 | observe | wait | `choose_action` 被问次数 |
|---|---|---|---|---|
| dev-reference | 7,943 | 91 | 7,852 | **~91** |
| demo-week | 299 | 52 | 247 | **~52** |
| mine-s7 | 1,181 | 52 | ~1,139 | **50**（诊断实计） |

三条推论：

1. **等待不花钱。** `score_report.wait_seconds = {explicit: 7,052,700, unavailable: 7,052,700}`
   两值相等 ⇒ 所有等待都属「无可行动天区」，`avoidable_wait`（0.001/s）**从未计费**。
   花钱的是**咨询名额**，不是时间。问题的真实形状是「把 ~90 个名额分给谁」。
2. **A6（分区配额兜底）已被否证。** `mine-s7` 上 R03/R04 只在 50 次咨询里的 **7 次**出现在候选板上
   （另 43 次根本不在），贪心在那 7 次里已取 3 次 ⇒ 那 700 分缺口源于**合法窗口稀缺**，不是排序错。
   装上 `quota-floor` 后：mine-s7 **−1.77**、demo-week **+24.64**，而两场景 `tiles` 与罚分**都没变**
   —— 它只是在换天区。另注：`terminal_penalty_avoidance`（FLEXIBLE 100）**已经在平台的
   `estimated_total_gain` 里**，再按配额插队等于把同一笔钱算两遍。
3. **A7 成立：** 咨询次数是小数字，所以「每次咨询调一次模型」在 7200 s 预算下**可负担**
   （确定性基线自身消耗 526.73 s ÷ 91 次咨询 ⇒ 每次还剩 ~6.6 s）。
   这推翻了我先前「LLM 在算术上不成立」的论证 —— 那个分母用了时隙数 7,900，真实分母是咨询数 91。
   SKILL.md 的 `wallclock / expected_decisions` 防的是每时隙重活。**仍然保留的约束**：
   墙钟与咨询次数在隐藏场景都未知 ⇒ 任何 LLM 分支必须带墙钟守卫，吃紧即降级为确定性。

dev-reference（180 夜）与 mine-s7（30 夜）在**结构上**的差别仍然成立，只是它不带来可抢的分：
前者 64/64、罚分 0、均匀度 1.00；后者 52/64、`flexible_shortfall` 700（R03 缺 3、R04 缺 4），
且终止原因仍是 `survey_complete` —— 不是墙钟到点，是窗口轮不到。

复现：

```bash
python harness/make_scenario.py --out harness/scenarios/mine-s7 --seed 7 --days 30
python scripts/ao.py run --scenario mine-s7 --strategy greedy
python scripts/ao.py run --scenario mine-s7 --strategy analysis/diag_quota.py   # [diag] 行在 agent.log
```

`runs/` 不进 git（见 `.gitignore`）；真要留一次运行的 `decisions.csv`，
复制成 `submissions/<日期>-<场景>-<策略>.csv` 再在这里引用。

## 已上传平台的提交

| 日期 | 场景 | 文件 | 平台分数 | 榜单名次 | 备注 |
|---|---|---|---|---|---|
| — | — | — | — | — | 尚无提交 |
