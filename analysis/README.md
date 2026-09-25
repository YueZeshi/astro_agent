# analysis/

**唯一允许读 `harness/scenarios/**` 真值数据的层。** 这里的代码永远不被提交、永远不被 `agent/`
import —— 一旦哪个函数被复制进策略，就越过了规则边界（[红线](../README.md#红线先读这段再写代码)）。

练习场景的 `weather.csv` 与 `weather_forecasts.csv` 由 `weather_metadata.json` 标为
`participant_visible`，所以**离线**复盘它们是合法的；运行时读它们是违规的。

## 待做的两项分析

### A1 全知上界 —— 决定后面所有事值不值得做

对每块天区枚举其合法时隙（高度角 ≥ 30°、在 `available_from_utc…available_until_utc` 内、
`is_observable`），用真值天气算 `A_used`，取 `max`，汇总：

```
ceiling = Σ_tile  V_tile × max_t A_used(t) × (1 + program_bonus[band(max_t)])
```

与 P0 = **12,287.478365**（其中 `base_science` 7,178.82 + `program_bonus` 1,188.66 +
`request_reward` 3,920.00）比较，直接回答：

> 基线已经把覆盖、请求、罚分三项打满。剩下的 `base_science + program_bonus = 8,367.48`
> 到底能涨到多少？是 5% 还是 60%？

这个数决定策略该投在「挑时刻」还是「别的维度」。档位一项的上界已经从分项算出是 **+4.9%**
（见 [strategy-design.md](../docs/strategy-design.md#1-先定位余量在哪)），`A_used` 的上界还没算。

注意：`lunar_quality_factor` 与 `airmass` 需要逐时隙几何，而 `tile_windows.csv` 只发布了
前 3 晚（135 行）。要么复用 `harness/challenge/tile_geometry_simulator.py`（离线，允许），
要么退到窗口级 `best_airmass` / `mean_lunar_quality_factor` 做近似上界 —— 近似值必须标注。

### A2 预报校准 —— 给「要不要等」提供可靠概率

`weather_forecasts.csv` 有 189 行、带 `revision`（每日修订）、`probability`、
`start/end_uncertainty_seconds`；生成器参数写的是漏检率 12%、6 个假阳性。

要产出的是**条件概率表**：给定 `condition`、`spatial_scope_type`、`probability`、
预报起始偏差，实际发生率与持续误差分别是多少。策略里那个「等 / 拍」的阈值应该由这张表定，
不该由直觉定。

事件类型分布（dev-reference）：`cloudy 10 / rainy 6 / smoggy 5 / cold_wave 4 /
rocket_launch 3 / tornado 1`；空间范围 `ALL 11 / HORIZON_SECTOR 9 / REGION_SET 7 /
SKY_CAP_ICRS 2`。

## 约定

- 脚本命名 `<问题>.py`，产出写进本目录的 `out/`（gitignore）。
- 任何进 `agent/` 的东西必须是**结论**（一个数、一条判据），不能是这里的代码。
- 上界类结论一律带「近似 / 精确」标注和计算前提，并同步到
  [submissions/LEDGER.md](../submissions/LEDGER.md) 或 `docs/strategy-design.md` 的待验证清单。
