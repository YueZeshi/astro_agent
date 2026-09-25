# 数据字典 · Data dictionary

场景目录结构（`harness/scenarios/<name>/`）由 `scenario_manifest.json` 用 SHA-256 逐文件钉死。
**改了任何一个字节，分数就不再可比。** 别动。

```
scenarios/<name>/
├── config/                     # 7 个规则配置文件（评分常数的真值来源）
│   ├── scenario_config.json    # 场景 id / seed / 墙钟 / 合约语义
│   ├── score_config.json       # 评分项与罚分 —— 见 scoring.md
│   ├── calendar_config.json    # 台址、夜定义、仿真步长
│   ├── tile_config.json        # 天区网格、几何、月相模型、目标分布
│   ├── weather_config.json     # 天况噪声模型、闭合概率、预报精度
│   ├── request_config.json     # 观测请求下发节律与奖励
│   └── workflow_config.json    # 墙钟、周期地平线
└── outputs/reference/          # 真值数据 —— 智能体运行时【拿不到】这个目录
```

## 运行时可见 vs 不可见

`weather_metadata.json` 自己声明了分类：

```json
"participant_visible":  ["weather.csv", "weather_forecasts.csv"],
"organizer_internal":   ["weather_events.csv"]
```

但要分清两件事：

| 数据 | 在参考目录里公开？ | 智能体运行时能拿到？ |
|---|---|---|
| 天况真值 `weather.csv` | 是（练习场景） | **否** —— 只拿得到当前快照天况 + 每块候选的 `effective_weather`，且被剥掉 `instrument_efficiency`、抹掉故障 |
| `weather_forecasts.csv` | 是 | 是，经 `weekly.weather_forecast` 修订版本下发 |
| `weather_events.csv`（事件真值） | **否，永远** | 否 |
| `tile_anomalies.csv`（隐藏标签） | **否，永远** | 否 |

所以练习场景可以**事后**复盘「我当时的判断差多远」，但策略里读不到。唯一合法的预测手段是
`weekly.weather_forecast` + 已观测到的历史。想拿 `weather.csv` 训模型 = 违规。

## dev-reference 实测画像

`scenario_id = example3-reference-seed-20260909`，seed 20260909，墙钟 7200 s。

| 文件 | 行数 | 列 |
|---|---|---|
| `night_calendar.csv` | 180 | `night_id, night_date, solar_dusk_utc, solar_dawn_utc, observing_start_utc, observing_end_utc, night_seconds, slot_count` |
| `slots.csv` | 7928 | `slot_id, night_id, timestamp_utc, duration_seconds` |
| `tiles.csv` | 64 | `tile_id, ra_deg, dec_deg, nominal_exptime_seconds, region_id, scheduling_class, available_from_utc, available_until_utc, n_lrg, n_elg, n_qso, n_bgs` |
| `targets.csv` | 15833 | `target_id, tile_id, target_class, feature_flux, redshift, science_weight` |
| `tile_windows.csv` | 135 | `window_id, night_id, night_date, tile_id, window_start_utc, window_end_utc, window_seconds, best_time_utc, best_airmass, mean_airmass, mean_lunar_quality_factor, minimum_lunar_quality_factor, region_id, scheduling_class, nominal_exptime_seconds, available_until_utc` |
| `observation_requests.csv` | 18 | `request_id, issued_at_utc, available_from_utc, deadline_utc, deadline_class, completion_mode, required_tile_count, completion_reward, miss_penalty, reason` |
| `observation_request_tiles.csv` | 31 | `request_id, tile_id, required_visits` |
| `weather.csv` | 7928 | `slot_id, night_id, timestamp_utc, duration_seconds, is_observable, seeing_arcsec, transparency, sky_quality, instrument_efficiency` |
| `weather_forecasts.csv` | 189 | `forecast_id, event_id, revision, issued_at_utc, condition, predicted_start_utc, predicted_end_utc, spatial_scope_type, spatial_scope_payload, severity, probability, start_uncertainty_seconds, end_uncertainty_seconds` |
| `weather_events.csv` | 29 | `event_id, condition, actual_start_utc, actual_end_utc, spatial_scope_type, spatial_scope_payload, severity, force_close, seeing_multiplier, transparency_multiplier, sky_quality_multiplier, instrument_efficiency_multiplier` |

三个场景同构，规模差异：

| | demo-week | dev-reference | finals-preview |
|---|---|---|---|
| 夜 / 时隙 | 7 / 294 | 180 / 7928 | 7 / 294 |
| targets | 15,960 | 15,833 | 16,300 |
| tile_windows | 150 | 135 | 153 |
| 请求 / 请求天区 | 1 / 2 | 18 / 31 | 1 / 1 |
| 预报 / 事件 | 97 / 29 | 189 / 29 | 99 / 30 |
| `tile_anomalies` | — | —（文件不存在） | 4 |
| 墙钟 | 900 | 7200 | 900 |

## 结构事实（策略设计的输入）

- **天区**：8 分区 × 8 块 = 64。每分区 2 块 `REQUIRED`（其中 1 块窗口只有 14 天），
  共 16 REQUIRED / 48 FLEXIBLE。`dec ∈ [−5°, 65°]`。
- **曝光时长分布**：450 s×10、600 s×9、900 s×18、1200 s×15、1350 s×12 → **全survey只需 60,300 s 曝光**。
- **时隙供给**：7928 × 900 s ≈ 7.14 M s。**时间极度过剩，稀缺的是每块天区的合法窗口。**
  这决定了 dev-reference 上不是「抢时间」，而是「在有限窗口里挑到最好的那一晚」。
- **`tile_windows.csv` 只覆盖前 3 晚**（2026-09-07…09）：它是发布出去的一个 7 天地平线切片，
  不是全场表。运行时的窗口靠每晚 `night_start.tile_windows` 与 `weekly` 增量下发。
- **天况实测分布（仅开放时隙）**：`seeing` 0.551–1.679（中位 1.162）、`transparency` 0.577–1.0
  （0.824）、`sky_quality` 0.556–1.301（0.961）、隐藏的 `instrument_efficiency` 0.709–1.0（1.0）。
  393/7928 时隙闭合（4.96%）。
- **事件类型**：`cloudy 10`、`rainy 6`、`smoggy 5`、`cold_wave 4`、`rocket_launch 3`、`tornado 1`；
  空间范围 `ALL 11 / HORIZON_SECTOR 9 / REGION_SET 7 / SKY_CAP_ICRS 2`。
- **请求**：`ONE_WEEK 6 / TWO_WEEKS 7 / ONE_MONTH 5`，`ALL 11 / AT_LEAST_N 7`；
  每块所需天区 `reward 140` / `miss 190`（所以 `completion_reward = 140 × required_tile_count`）。
- **目标类别**：ELG 6238、BGS 4654、LRG 3787、QSO 1154；`V_tile` = 各目标 `science_weight` 之和。
- **节律**：每 7 晚下发一次请求（`occurrence_probability 0.55`），预报地平线 7 天，
  预报漏检率 12%、6 个假阳性、每日修订。

## 元数据文件

`catalog_metadata.json`：airmass 取瞬时天顶归一值；`lunar_quality_factor` 在 (0,1] 连续，
月落时为 1。`calendar_metadata.json`：`slot_count_range [37,47]`，区间语义
**半开 `[start, end)`**。`observation_request_metadata.json`：deadline 分布计数。
`weather_metadata.json`：上面那份可见性表 + 各类 SHA-256。
`scenario_manifest.json`：逐文件行数与哈希、墙钟。

## 造自己的场景做泛化验证

隐藏场景 = 同一生成器、未知 seed。所以**必须**自己造场景：

```
python harness/make_scenario.py --out harness/scenarios/mine-a --seed 7 --days 90 --start-date 2026-10-05
python scripts/ao.py run --scenario mine-a
python scripts/ao.py score --run runs/<id>
```

`make_scenario.py` 默认基于 dev-reference，可配 `--regions --tiles-per-region --wallclock --validate-only --force`；
生成结果跨操作系统字节一致。SKILL.md 明确要求：**多个 seed + 至少一个 ≥ 90 夜的长场景**。
`fetch_scenario.py --list` 看平台上还发布了哪些公开场景（如 `dev-fortnight`）可拉下来跑。
