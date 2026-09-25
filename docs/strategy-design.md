# 策略设计 · Strategy design

本页回答一个问题：**分数还能从哪里来。** 不是罗列点子，是排除掉不值得做的点子。

## 1. 先定位余量在哪

P0 锚点：`greedy`（官方默认，取 `candidates[0]`）在 `dev-reference` / 墙钟 7200 s 实测
**12,287.478365**，与官方 `/brief` 公布的 reference 分数逐位一致。分项：

| 分项 | 实测值 | 占总分 | 还有余量吗 |
|---|---|---|---|
| `base_science` | 7,178.82 | 58.4% | ✅ **主战场** |
| `program_bonus` | 1,188.66 | 9.7% | ✅ 见下 |
| `request_reward` | 3,920.00 | 31.9% | ❌ 17 完成 + 1 豁免，0 罚分 |
| `coverage_bonus` | 0.00 | — | ❌ `score_config` 里没有权重键 |
| `report_reward` | 0.00 | — | ❌ 练习规则下上报动作非法 |
| `penalties` | 0.00 | — | ❌ 已经全零（64/64 块、`required_miss` 0、`flexible_shortfall` 0） |
| `coverage_evenness` | **1.00** | — | 已完成天区在 8 个分区间绝对均匀（每区 6 块） |

**档位杠杆的上界**：实测 `program_bonus / base_science = 16.56%`，而最高档 DARK 是 25%。
若所有观测都落在 DARK 档且 `base_science` 不变，可加 `0.0844 × 7,178.82 ≈ +606`，即 **+4.9%**。
这是「只挑质量、把 band 顶过 0.65」这一项的理论上限（真实值会更低，因为强行等待会丢窗口与科学分）。

时间也不是约束：全场 64 块天区共需 **60,300 s** 曝光，而场景给了 **7928 × 900 s ≈ 7.14 M s** 的夜时间
（约 118 倍冗余）。稀缺的是**每块天区各自那几个合法窗口**。

> **结论（仅限 180 夜的 dev-reference）：这个场景上唯一的分数来源，是把每块天区拍在它自己
> 窗口里质量最高的那个时刻。** 覆盖、请求、罚分三项基线已经打满；「抢时间 / 排产顺序」类优化
> 收益为 0，全部余量在 `base_science` + 档位（上界 **+4.9%**）。

## 1b. 但这条结论不普适 —— 30 夜场景上基线立刻开始漏分区

把同一个 greedy、同样 7200 s 墙钟放到自造的 30 夜场景 `mine-s7` 上：

- total **4,483.429216**，完成 **52/64**，`flexible_shortfall` **700.00**
  （`required_miss` 0、`request_miss` 0），且终止原因仍是 **`survey_complete`** ——
  **不是墙钟到点，是每块天区的合法窗口在 30 夜里根本轮不到。**
- 分区 FLEXIBLE 完成数：六个分区各 6 块，但 **R03 只 1 块、R04 整区 0 块**。
  `flexible_quota_per_region = 4` ⇒ R03 缺 3、R04 缺 4，7 × 100 = 700。

greedy 按 `estimated_gain_per_second` 逐时隙取最优，**完全不看分区配额**，于是时间余量一低
就有整块分区被饿死。所以：

| | dev-reference (180 夜) | mine-s7 (30 夜) |
|---|---|---|
| 时隙数 | 7,928 | 1,181 |
| **`choose_action` 实际被问次数** | **91** | **50** |
| 其中缺口分区在候选板上的次数 | — | **7**（另 43 次根本不在） |
| 主战场 | `base_science` 挑时刻 | 同样是挑时刻 —— 配额缺口抢不回来 |

**但「靠优先补配额抢回那 700 分」这条已被实测否证。** 诊断（`analysis/diag_quota.py`）显示
R03/R04 只在 50 次咨询里的 7 次出现在候选板上 —— `_finalize` 在「没有拍得完的候选」时直接
返回 wait，**压根不问策略**。贪心在这 7 次里已经取了 3 次。缺口的成因是**合法窗口稀缺**，
不是优先级排错。把 `quota-floor` 真装上以后：`mine-s7` **−1.77**、`demo-week` **+24.64**，
而两个场景的 `tiles` 与罚分**都没变** —— 它只是在换天区，不是在补配额。

⇒ 问题的真实形状：**每场只有 ~50–90 个「现在确实拍得完」的机会**，决策是把这几十个名额
分给谁。等待不花钱（`avoidable_wait` 在实测里从未计费，见
[scoring.md §5](scoring.md#实测真正的决策次数是个小数字)），花钱的是**名额**。
`terminal_penalty_avoidance`（FLEXIBLE = 100）**已经在平台的 `estimated_total_gain` 里**，
所以再按配额插队等于把同一笔钱算两遍，必然掉分。

**隐藏场景的 `days` / `n_slots` / 墙钟都不公开**，而咨询次数随场景变化 —— 所以
「按剩余夜数 pacing」这类规则不可实现（快照里没有总夜数），任何预算判断只能用
**自己能量到的墙钟消耗比例**。

## 2. 质量的杠杆有多长

```
A_used = eff × transparency × sky_quality / (seeing × airmass)  × lunar_quality_factor
```

用 `dev-reference/weather.csv` 开放时隙的实测边际范围（见
[data-dictionary.md](data-dictionary.md#结构事实策略设计的输入)）：`seeing` 0.551–1.679、
`transparency` 0.577–1.0、`sky_quality` 0.556–1.301、隐藏 `eff` 0.709–1.0。

同一块天区，在最差合法时刻与最好合法时刻之间，`A_used` 差**数倍**；再叠上档位跳变
（`combined_quality` 过 0.65 → DARK，加成从 0.15 变 0.25）。
所以一次好选择 ≈ 一块天区的分数翻倍，而等待的代价是 0.9 分/时隙。**比值上完全划算。**

⚠️ 但这正是最容易死的地方：**等待到窗口结束 = `invalid_action` −100 或科学分 0；
错过 REQUIRED = −1000。** 「天况不好就等」这条看着最合理的规则，官方实测 **−1,700**。

## 3. 为什么「等」是危险的，以及怎么把它做对

`estimated_gain_per_second` 是**贪心**排序 —— 它看不见两笔延后结算的账：

1. 窗口耗尽：块天区 `available_from_utc … available_until_utc`，其中 1 块限时 REQUIRED 只有 **14 天**。
2. 收官结算：REQUIRED 漏 −1000、分区 FLEXIBLE 不足 4 块每块 −100、请求过期 −190/块。

正确形态不是「质量不够就等」，而是**带截止时间的可选延迟**：

```
每个候选的即时收益 = estimated_total_gain（平台已算）
每个候选的延迟价值 = 未来同一块天区上期望更高的 A_used × 概率 − 风险
只有当「还能等」且「等了大概率更好」时才等
「等不了了」（剩余合法机会 < 阈值）→ 立刻拍当前最好的
```

`reference.py` 就是这个形状（`remaining_chances()`、`LAST_CHANCES = 2`），但它的两条覆盖类规则
在练习场景上是空转的（`coverage_bonus` 权重为 0），而它的「等天况」分支被 `if False` 关掉 ——
所以**它在 dev-reference 上实测只能和贪心基线打平**。要打穿，就得把「等」建立在对预报的
量化判断上，而不是关掉它。

## 4. 真正没被榨干的信号：7 晚窗口表 + 7 天预报

实测（`analysis/probe_strategy.py`，见 [agent-protocol.md](agent-protocol.md)）：基线完全没用
两份**已经公开发给它**的数据：

1. **`weekly.tile_windows`：未来 7 个夜晚、359 行，每行带 `best_time_utc`、`best_airmass`、
   `mean_lunar_quality_factor`。** 也就是说「某块天区接下来哪天几点条件最好」是**公开可算的**，
   不需要预测。这一份直接支撑第 1 节的 `base_science` 余量。
2. **`weekly.weather_forecast`**：带 `revision`（每日修订）、`probability`、
   `start/end_uncertainty_seconds`，**漏检率 12%、6 个假阳性**。这是唯一需要概率化使用的部分。

两者都要缓存进 `memory` —— `weekly` 每 7 晚才发一次，不是每晚都发。
`night_start.tile_windows` 只有当晚，`weekly.tile_windows` 才有 7 晚跨度。

注意 `cold_wave`：预报里有 `cold_wave` 覆盖的时隙，观测读数不可信
（`anomaly_detection.py` 明确要求丢弃），正式赛里会影响上报判据。

## 5. 泛化：隐藏场景才是真正的对手

评测 = 真实数据 + **隐藏场景** + 代码质量/文档。隐藏场景来自同一生成器、未知 seed / 规模 / 墙钟。
已知会变的：

- `global_wallclock_seconds`（finals-preview 只有 **900 s**，dev-reference 7200 s —— 7.9 倍差）
- 规模（`make_scenario.py` 可造 1600 天区级；覆盖类打法在 1600 规模上实测 +2.00%）
- `schema_version` v2 vs v3（重复观测、上报、异常标签、覆盖奖励**只在 v3 生效**）
- `score_config` 常数本身

**所以任何硬编码都是债。** 常数从 `initialize.scoring_contract.score_config` 读，
墙钟从 `initialize.global_wallclock_seconds` 读，规则代际从 `snapshot.schema_version` 读。

三条设计约束：

1. **不针对 64 块天区调参。** 用 `make_scenario.py` 造 ≥ 90 夜的多个 seed 场景验证。
2. **同一份策略要在 v2 和 v3 上都成立。** v3 上重复观测合法 ⇒ 可以「先拍一次保底、
   之后遇到更好窗口再刷」；v2 上重复即 `duplicate_tile` −100 ⇒ 必须一次到位。
   这是一个必须分支的行为差异，不是调参。
3. **预算自适应。** 墙钟 900 s 时不可能慢慢等 —— 等待策略必须按剩余预算收敛到贪心。

## 6. 待验证清单（按期望收益排序）

| # | 假设 | 验证方法 | 风险 |
|---|---|---|---|
| A1 | 把每块天区从「首个合法时刻」推到「窗口内最优时刻」能显著提升 `base_science` | 用公开 `weather.csv` **离线**算全知上界，和基线比 | 中：受窗口数限制，可能余量比想象小 |
| A2 | 预报投影能给出可靠的等待/拍摄判据 | 回放 `weekly` 修订 vs 事后真值，算校准误差 | 中高：12% 漏检 + 6 假阳性 |
| A3 | v3 上「保底 + 刷分」两轮打法优于单轮 | 在 finals-preview + 自造 v3 场景跑 | 低：v2 上必须关掉 |
| A4 | 墙钟比例控制器（剩余预算 / 剩余必需曝光）能防崩 | 扫 `--wallclock` 从 900 到 7200 | 低 |
| A5 | LLM 只在预报解读上有增益 | 对照 `MODEL_PROVIDER=deterministic` | 高：延迟与 3 次/轮上限 |
| ~~A6~~ | ~~分区配额兜底~~ | **已否证**：`quota-floor` 在 mine-s7 −1.77、demo-week +24.64，两场景罚分与完成块数均未变。缺口来自合法窗口稀缺（缺口分区只在 7/50 次咨询里出现在候选板上），不是排序 | — |

A6 的否证顺带产出 A7 —— **它才是真正的结构性发现**：

| # | 假设 | 验证方法 | 风险 |
|---|---|---|---|
| A7 | 每场只有 ~50–91 次真实咨询，所以「每次咨询调一次模型」在 7200 s 预算下可负担（527 s 基线开销，剩 ~6.6 s/次） | 加一个每次咨询调模型的分支，测 `accounted_wallclock_seconds` 与 `global_wallclock_expired` | 隐藏场景墙钟与咨询次数都不公开 ⇒ **必须带墙钟守卫**，预算吃紧即降级为确定性 |

A1 优先 —— 它决定后面所有值不值得做。**全知上界必须在离线分析里算，绝不能在策略里读。**
运行时读 `weather.csv` 是违规（[competition.md § 红线](competition.md#红线来自规则页与-skillmd)）。

## 7. 实验纪律

- 一次一个改动，跑完就在 `submissions/LEDGER.md` 记一行：策略名、场景、seed、总分、各分项、结论。
- **不要用 dev-reference 的单次分数下结论。** 它是固定 seed 的一个样本；至少在 2 个自造
  ≥ 90 夜场景上同向，才允许提升为「更好」。
- 分数没变就不要提交（10 次/天的额度是真实预算）。
- 每次 `ao.py run` 之后 grep `agent.log` 里的 fallback 关键字 —— 静默降级成基线是最难发现的 bug。

见 [experiment-protocol.md](experiment-protocol.md)。
