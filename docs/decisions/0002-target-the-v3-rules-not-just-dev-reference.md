# ADR 0002 · 面向 v3 正式规则设计，而不是只面向 dev-reference

- 状态：已接受（2026-09-25）

## 背景

评测口径是「真实数据 + 隐藏场景 + 代码质量与文档」。两代规则同时在跑：

- `dev-reference` / `demo-week`：`score_config` 里没有 `repeat_observation` / `reporting` /
  `anomaly_tags` / `fault_response` / `coverage_bonus_weight`，快照为 `decision-snapshot-v2`。
  重复观测 = `duplicate_tile` −100，上报 = `unknown_action`。
- `finals-preview` 及其隐藏同类：上述键齐全，快照 `decision-snapshot-v3`，另有隐藏异常标签、
  故障上报、`coverage_bonus_weight = 0.35`、墙钟仅 **900 s**（dev-reference 是 7200 s）。

隐藏场景不公开、由主办方另行运行。只按 dev-reference 能观察到的行为写策略，等于按一个
被阉割的规则子集调参。

## 决定

1. 策略必须**先读 `snapshot.schema_version` 再决定行为**，而不是假设某条规则存在。
   判据统一走 `score_config` 里有没有那几个键（与官方
   `anomaly_mechanics_enabled()` 一致）。
2. 评分常数**一律从 `initialize.scoring_contract.score_config` 读**，不硬编码
   1000 / 140 / 190 / 0.65 / 0.40。墙钟从 `initialize.global_wallclock_seconds` 读。
3. 验证集必须包含 v3：`finals-preview` + 自造场景。dev-reference 单点提升不算证据。

## 后果

- 「v3 上先拍一次保底、之后遇到更好窗口再刷」在 v2 上是**扣分行为**，必须显式分支，
  这是策略里唯一一处硬二元开关，不接受折中。
- 等待类策略必须按剩余预算收敛（900 s 与 7200 s 是两种截然不同的最优）。
- 多写一层规则探测代码；换来的是隐藏场景不崩。值得。
