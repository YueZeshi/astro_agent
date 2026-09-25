# 评分模型 · Scoring

合约版本 `challenge-score-v3`。本页的常数全部从 `harness/scenarios/*/config/score_config.json`
与 `harness/challenge/scoring_core.py` 读出，不是网页转述。**改任何一个常数之前，先读代码。**

```
total = base_science + program_bonus + request_reward + coverage_bonus + report_reward − Σ penalties
```

`score_report.json` 里逐项给出，提交详情页给同一份构成 + 回放。同一场景 + 同一 `decisions.csv`
本地和平台分数**必须一致**（`input_sha256` 逐文件钉死）。

## 1. 一次观测的科学分

曝光被切成段（segment）逐段积分，每段：

```
A        = instrument_efficiency × transparency × sky_quality / (seeing_arcsec × airmass^1.0)
           不可观测 → 0；上限截断 maximum_weather_quality = 3.0
A_used   = A × lunar_quality_factor
base     = V_tile × (segment_seconds / nominal_exptime_seconds) × A_used × anomaly_factor
bonus    = base × program_bonus[program]        # 仅当 program == band
```

- `V_tile`：该天区所有目标 `science_weight` 之和，即公开的 `tile_science_value`。
- `airmass_exponent = 1.0`，`altitude_exponent = 1.0`，`minimum_altitude_deg = 30.0`。
- 月相：`lunar_quality_factor ∈ (0,1]`，`angular_decay_scale_deg = 35`，`maximum_penalty = 0.75`，
  月亮在地平线下时为 1。
- `anomaly_factor`：隐藏标签乘数，`nova ×1.5`、`reddening ×0.8`，可叠加。**只在正式规则里存在。**
- `instrument_efficiency` 在 **v3（正式规则）里被剥掉**：`_public_weather` 不把它放进
  `effective_weather`，也不放进 `current_site_weather`（本机实测）。但 **v2 练习场景的
  `current_site_weather` 仍带它**（demo-week = 1.0）—— 见
  [agent-protocol.md](agent-protocol.md#两份视图candidate_tiles-与-candidates实测别混)。
  **策略里不要写任何依赖该字段存在的代码，正式场景会 `KeyError`。**
  于是「实现分 / 预览分」的比值（`tile_last_finished`，仅 v3）就是隔离仪器侧信号的唯一探针。

### 关键推论：档位是「什么时候拍」的结果，不是独立旋钮

平台给每个候选算好 `combined_quality`（不含 efficiency 的那部分质量），并**按质量把 program 定档**：

| band | 门槛（combined_quality） | 加成 |
|---|---|---|
| `DARK` | ≥ 0.65 | +0.25 |
| `BRIGHT` | ≥ 0.40 | +0.15 |
| `BACKUP` | < 0.40 | +0.08 |

候选里的 `program` 已经等于 band。**结论：想拿 DARK 的 0.25 就得等到质量真正过 0.65 再拍 ——
加成不能靠填字段骗出来，填错反而丢加成。** 预览公式（`agent/scoring_preview.py:185`）：
`potential = tile_value × combined × (1 + bonus[band])`。

## 2. 什么算「完成一次曝光」

`apply_decision` 从 `remaining = nominal_exptime_seconds` 起逐段扣。全部条件：

1. 整段曝光**必须落在同一个 `night_id` 内**；
2. 起始时刻与每段**中点**都要合法：高度角 ≥ 30°，且 `available_from_utc ≤ t < available_until_utc`；
3. 该时隙 `is_observable` 为真。

`completed = (remaining == 0 and outcome == "completed")`。否则：

- `weather_interrupted` → 科学分 0，**不罚分**（天气不可控，规则明说「天气中断不罚」）。
- `geometry_or_night_interrupted` → 科学分 0 **且** 记一次 `invalid_action`（−100）。

一块天区的分数取**所有观测里的最高一次**（`repeat_observation.tile_score_aggregation = "max"`，
写别的值直接 raise）。一旦合法完成就入账，之后不必再拍。

## 3. 加分项

| 项 | 公式 | 备注 |
|---|---|---|
| `request_reward` | `140 × required_tile_count` | 完成请求。`satisfied` = 访问次数 ≥ `required_visits` 的天区数 |
| `coverage_bonus` | `W × base_science × Jain_evenness` | `evenness = (Σx)² / (n·Σx²)`，按分区统计已完成天区数 |
| `report_reward` | `+100` / 每个 (tile, tag) 首次判对 | 只在正式规则 |

`coverage_bonus_weight`：**dev-reference 与 demo-week 没有这个键（= 0）**，finals-preview = **0.35**。
练习场景刷不出覆盖分，别拿它调参。

## 4. 扣分项（`score_config.penalties` + 请求侧）

| key | 值 | 触发 |
|---|---|---|
| `unsafe_observation` | **2000.0** | 在不合法的时刻强行观测 |
| `required_miss` | **1000.0** / 块 | 必做天区整场没完成 |
| `request_miss` | **190.0** / 块（= 请求自带 `miss_penalty`） | 请求过期未完成 |
| `flexible_shortfall_per_tile` | **100.0** / 块 | 分区完成的 FLEXIBLE 不足 `flexible_quota_per_region = 4` |
| `invalid_action` | **100.0** | 也覆盖 `unknown_slot` / `stale_decision` / `duplicate_tile` / `outside_tile_window` / `invalid_request_tag` / `invalid_observe` / 几何或入夜结束导致的中断 |
| `wrong_tag_report` | **150.0** | 报错异常标签 |
| `fault_misreport` | **100.0** | 超过 `fault_misreport_free_allowance = 1` 的误报 |
| `avoidable_wait_per_second` | **0.001** / 秒 | **只在当时确实有可行动天区时**才计 |

`interrupted_exposure_science_score = 0.0`，`one_ordinary_credit_per_tile = true`。
天气导致「本来该做但做不了」的请求记 `excused_unobservable`，**免罚**。

上报期望值：对一条 +100、错一条 −150 → **猜中率 60% 才不亏**。自带判据
（`agent/anomaly_detection.py`）：NOVA 比值带 1.30–1.65、Reddening 0.70–0.87、故障 ≤ 0.60，
要求 ≥ 5 次读数中 ≥ 80% 落在带内且跨 ≥ 2 晚，或滚动 6 次读数窗口内 2 次塌陷。
`cold_wave` 预报覆盖期间的读数必须丢弃。故障上报后 `end_overrides` 推到
`as_of + repair_duration_days(2)`，并在 `response_latency_days(1)` 后公布。

## 5. 时间预算：唯一的硬约束是全局墙钟（但智能体被问的次数远少于时隙数）

- **没有每次决策超时**（`per_decision_timeout = null`），**没有兜底合成动作**。
- 只有 `global_wallclock_seconds`：dev-reference = 7200，finals-preview = 900，隐藏场景自己发布
  （`initialize.global_wallclock_seconds` + 环境变量 `SAC_WALLCLOCK_SECONDS`）。
- **读快照不推进仿真时间，提交动作才推进。** 墙钟到点即杀，在途响应作废，
  未完成的 REQUIRED 每块 −1000。
- 退出码：`survey_complete` / `global_wallclock_expired` → 0；`agent_error` / `agent_initialization_error` → 2。

### 实测：真正的决策次数是个小数字

`decisions.csv` 里绝大多数行不是智能体的选择：

| 场景 | 行数（=时隙） | `observe` | `wait` | 其中 `no legal observable candidate can finish in its known window` |
|---|---|---|---|---|
| dev-reference | 7,943 | **91** | 7,852 | **7,852（全部）** |
| demo-week | 299 | **52** | 247 | 247（全部） |

`agent/decision_graph.py:_finalize` 在 `previews` 为空时**直接返回 wait，根本不调用
`my_strategy.choose_action`**。所以：

1. **`choose_action` 每场只被问 ~50–90 次**，只发生在「此刻确实拍得完某块天区」的机会上。
   SKILL.md 让人按 `wallclock / 时隙数` 预算每次决策，那个分母**过于悲观**（它防的是每时隙重活）。
   按 dev-reference 实测：527 s 基线开销 + 91 次咨询，7200 s 预算下**每次咨询还剩 ~6.6 s**，
   所以「每次被问时调一次模型」在算术上是可行的 —— 但见 [agent-protocol.md](agent-protocol.md)
   的守卫要求。
2. **`avoidable_wait`（0.001/s）在这些场景里根本没被计费**：
   `score_report.wait_seconds = {explicit: 7,052,700, unavailable: 7,052,700}` —— 两者相等，
   说明所有等待都是「无可行动天区」的等待，不罚。
   ⇒ **「拍还是等」不是每秒权衡，而是「这次机会给哪块天区」的稀疏分配问题。**
   等待本身不花钱，花掉的是那个**只有 91 个的咨询名额**。

## 6. 两代规则并存 —— 先看 `schema_version`

判据是 `anomaly_mechanics_enabled(score_config)`：`score_config` 含
`repeat_observation` / `reporting` / `anomaly_tags` / `fault_response` 任一即为正式规则。
智能体侧的信号是快照的 `schema_version`：v3 = 正式（另有 `tile_last_finished`、`fault_status`），v2 = 练习。

| | 练习（dev-reference / demo-week） | 正式（finals-preview 及隐藏场景） |
|---|---|---|
| 重复观测 | **非法**，记 `duplicate_tile` −100 | 合法，取最高分 |
| 上报动作 | **非法**，`unknown_action` | 正确 +100 / 错误 −150 |
| 隐藏异常标签 | 无（也没有 `tile_anomalies.csv`） | nova ×1.5 / reddening ×0.8 |
| 覆盖奖励 | 权重 0 | 0.35 |

**任何只针对 v2 写的策略都会在隐藏场景上翻车**，隐藏场景大概率是 v3。见
[ADR 0002](decisions/0002-target-the-v3-rules-not-just-dev-reference.md)。

## 7. 参照分数

| 场景 | 基线 total | 规模 |
|---|---|---|
| demo-week（本机实测 2026-09-25） | **5,909.099093** | 7 晚 / 294 时隙 / 52 块完成 / 1 请求（+280）；penalties 仅 flexible_shortfall 500；`runner_seconds` 20.05 |
| dev-reference（本机实测，与官方 `/brief` 逐位一致） | **12,287.478365** | 180 晚 / 7928 时隙 / 64 块全完成 / 17 请求完成 + 1 `excused_unobservable` / 0 罚分；分项见 [strategy-design.md](strategy-design.md#1-先定位余量在哪) |
| finals-preview（官方公布值，本机未复算） | ≈ **8,214.26** | 7 晚 / 294 时隙 / 30 事件 / 4 标签 |

前两个数是本机 `greedy`（= 官方默认 `minimal_agent` + 未改动的 `my_strategy`）跑出来的，
可在 `runs/*/score_report.json` 复核。用 `12,287.478365` 而不是网页上的近似值作为 P0 锚点。

`coverage-aware` 打法在 1600 天区规模场景实测比贪心基线 **+3,980（+2.00%）**，且科学分与均匀度双赢
（137,674 vs 136,292；evenness 0.856 vs 0.811）。反例：「天况不好就主动等」实测 **−1,700** ——
等待只扣 0.001/秒，但错过的气象窗口不回来。
