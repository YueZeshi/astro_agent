# 智能体合约 · Agent protocol

来源：`harness/agent/protocol.py`（不是网页转述）。

```
PROTOCOL_VERSION             = participant-agent-protocol-v2
INITIAL_PUBLICATION_VERSION  = initial-publication-v2
DECISION_SNAPSHOT_VERSION    = decision-snapshot-v3      # 正式规则
ACCEPTED_PROTOCOL_VERSIONS   = (v1, v2)                  # 练习场景仍说 v1
ACCEPTED_SNAPSHOT_VERSIONS   = (decision-snapshot-v2, v3)
```

**传输**：JSON-Lines，一行一个对象。stdin = 平台 → 智能体，stdout = 智能体 → 平台。
stderr 全部进 `runs/<id>/agent.log`，所有诊断写那里。**stdout 只准出现协议行。**

语言无关：任何能吃 stdin、吐 stdout 的程序都行。`local_runner.py` 用
`[--python <interp>, "-B", <entry>]`、`cwd = agent 目录` 启动；`--agent` 可以给文件，也可以给
目录（按 `minimal_agent.py` → `agent.py` → `main.py` 找入口）。用 `--python node` 之类换解释器，
或 `harness/challenge/run_challenge.py --agent-command <cmd…>`。

环境变量：`PATH/HOME/TMPDIR/LANG/LC_ALL/PYTHON*` 被清洗过，加上你 `.env` 里的 `KEY=VALUE`，
再加 `PARTICIPANT_PROTOCOL`、`SAC_SCENARIO`、`SAC_WALLCLOCK_SECONDS`、`SAC_LOCAL_RUNNER=1`。
`--inherit-env` 改为透传你的 shell。

## 1. `initialize`（一次，30 s 内接受，不需要回复）

`payload`：

| key | 内容 |
|---|---|
| `schema_version` | `initial-publication-v2` |
| `calendar` | `first_night, last_night, night_count, slot_count, slot_duration_seconds` |
| `site` | `latitude_deg, longitude_deg, utc_offset_hours, sun_altitude_limit_deg` |
| `tile_catalog` | `tile_count, required_tile_ids, region_ids, tiles[]`（CSV 行 + `tile_science_value`） |
| `target_catalog` | 目标表 |
| `scoring_contract` | `score_config, weather_score_interface, lunar_model, preview_semantics` |
| `global_wallclock_seconds` | **本场的墙钟预算**，隐藏场景会换 |

`scoring_contract` 是合法读到评分常数的唯一途径 —— **策略里不要硬编码 1000 / 140 / 0.65，
从 `initialize` 的 `score_config` 里取**。隐藏场景可能改这些数。

## 2. `decision_request`（每个机会一次）

`decision_sequence` 同时出现在信封和 payload 里，两者不等即 `ProtocolError`。`payload`：

| key | 内容 |
|---|---|
| `schema_version` | `decision-snapshot-v3`（正式）/ `v2`（练习） |
| `cursor` | `slot_id, night_id, timestamp_utc, slot_offset_seconds` |
| `current_site_weather` | 台址当前天况 |
| `candidate_tiles` | 已按 `estimated_gain_per_second` 降序排好的合法候选 |
| `active_requests` | `{request_id, deadline_utc, completion_reward, miss_penalty, required_tile_count, satisfied_tile_count, is_complete, tile_requirements:[{tile_id, required_visits, completed_visits, remaining_visits}]}` |
| `night_start` | 每晚**第一次**决策才有：`{"night":…, "tile_windows":[…]}`，否则 `null` |
| `weekly` | 每 7 晚一次：`{issued_at_utc, weather_forecast, tile_windows, observation_requests}`，否则 `null` |
| `progress` | `{completed_tile_ids, flexible_completed_by_region}` |
| `tile_last_finished` | **仅 v3**：`{tile_id, score}` 或 `null` |
| `fault_status` | **仅 v3** |

### 候选对象

```
tile_id, region_id, scheduling_class (REQUIRED|FLEXIBLE), nominal_exptime_seconds,
tile_science_value, window_start_utc, window_end_utc,
geometry: {tile_id, timestamp_utc, altitude_deg, azimuth_deg, hour_angle_deg,
           airmass, moon_separation_deg, lunar_quality_factor},
effective_weather: {tile_id, is_observable, seeing_arcsec, transparency, sky_quality, active_event_ids},
already_completed
```

`challenge/challenge_workflow.py:_public_weather` **故意剥掉 `instrument_efficiency`**。
`effective_weather` 同时被故障与抹平处理过。用 `实现分 / 预览分` 的比值反推仪器侧，是唯一的探针。

`my_strategy.py` 拿到的候选是扁平化的预览视图（`agent/scoring_preview.py`）：

| 字段 | 含义 |
|---|---|
| `program` | 已由 `combined_quality` 定档（DARK/BRIGHT/BACKUP），**别改** |
| `request_id` | 不为 `""` 时这次观测服务某个请求 |
| `combined_quality` | 当前大气 × 月相质量（DARK ≥ 0.65，BRIGHT ≥ 0.40） |
| `estimated_science_score` | 该次曝光的期望科学分 |
| `terminal_penalty_avoidance` | 这次观测避免的收官罚分（REQUIRED 1000 / FLEXIBLE 100） |
| `request_policy_value` | 所服务请求的奖励或避免的过期罚 |
| `estimated_total_gain` | 以上合计 |
| `estimated_gain_per_second` | `estimated_total_gain / nominal_exptime_seconds` —— **默认排序依据** |

## 3. `decision_response`

```json
{"protocol_version":"participant-agent-protocol-v2","message_type":"decision_response",
 "decision_sequence":123,"action":"observe","tile_id":"T00012","program":"DARK",
 "request_id":"","reason":"...","decision_source":"strategy",
 "reports":[{"kind":"NOVA","tile_id":"T00019"}]}
```

- `action ∈ {observe, wait}`（`decisions.csv` 的合法动作另含
  `report_instrument_failure` / `report_nova` / `report_reddening`）。
- `program ∈ {DARK, BRIGHT, BACKUP}`，练习场景填 `""` 也可以。
- `reports` 可选，**上报不消耗时隙**。
- `decision_source` 标记这次决策来自 `deterministic` / `strategy` / LLM，回放里看得见。

## 4. `choose_action` —— 我们唯一必须写好的函数

`agent/my_strategy.py`：

```python
def choose_action(candidates, snapshot, memory):
    ...
```

返回值可以是：候选 dict（可先设 `candidate["reason"]`）、`int` 下标、`str` tile_id、或 `None` 表示等待。

- `candidates` 已排序，`[0]` 是每秒估计收益最高的一块。
- `memory` 是每次运行开始时创建的空 `dict` —— **除它之外没有任何东西跨决策存活**。
  别在模块级放状态：平台可能复用进程。
- 抛异常、返回非法候选、引用不存在的 `(tile_id, program, request_id)` → 落回默认排序 +
  stderr 记录（`agent/decision_graph.py:_strategy_decision`）。**不会崩，但会静默变基线**，
  所以每次跑完都要 grep `agent.log` 里的 `could not be imported` / `raised` / `not legal now`。

## 5. LLM 路径（可选）

`agent/model_factory.py` + `agent/.env`。`MODEL_PROVIDER=deterministic`（默认）不需要任何密钥、
网络、账号；改成 `openai` / `anthropic` 或任一 OpenAI 兼容端点
（`MODEL_PROVIDER` + `MODEL_NAME` + `MODEL_BASE_URL` + 对应 key）。
`requirements.txt` 里的 langchain / langgraph 只在走 LLM 时才需要 —— 平台会在全新 virtualenv 里
`pip install` 并放开网络。**约束：模型 ≤ 128K 上下文，每轮决策 ≤ 3 次调用。**
`LLM_TOP_K_CANDIDATES=12` 决定送进 prompt 的候选数。

确定性优先：隐藏场景墙钟可能只有 900 s，且评分要求同场景同 CSV 分数完全一致 ——
把 LLM 用在**决策质量真正需要判断的地方**（比如预报解读），其余交给确定性规则。
