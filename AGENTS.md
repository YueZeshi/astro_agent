# AGENTS.md

面向在本仓库工作的 agent。先读这一页，再读 `docs/`。

## 任务本质

为 GOSIM 2026「巡天智能体」写观测调度策略。评测 = 公开场景 `dev-reference` + **隐藏场景泛化** +
代码质量与文档。所以「在 dev-reference 上多拿 0.5 分」远不如「换个 seed、换个墙钟还不崩」重要。

## 目录规则（不可违反）

| 路径 | 可否修改 | 说明 |
|---|---|---|
| `harness/**` | ❌ **禁止** | 官方入门包逐字节副本（评分器、工作流、场景数据）。改了分数就与平台不可比 |
| `agent/**` | ⚠️ 仅 `my_strategy.py` 由 `ao.py select` 覆盖 | 提交单元；其余文件保持与官方一致，除非明确要改 `decision_graph.py` / `anomaly_detection.py` / `model_factory.py` |
| `strategies/**` | ✅ 主要开发场所 | 每份自包含，首行 `__strategy__ = "<name>"` |
| `scripts/ao.py` | ✅ | 只加封装，**不要**在封装里做任何评分 |
| `analysis/**` | ✅ | 唯一允许读 `harness/scenarios/**` 真值的层 |
| `docs/**`, `submissions/LEDGER.md` | ✅ | 交付物的一部分，会被评审 |

## 写策略时的硬约束

- 只用标准库，除非同时改 `agent/requirements.txt` 并接受 LLM 路径的延迟与配额。
- 不能 import 仓库里任何其他模块 —— 平台上只有 `agent/`，没有 `challenge/`、没有 `strategies/`。
- 运行时读不到场景文件、其他队伍数据、真实天气、仪器效率、隐藏标签。**别假装能读。**
- `memory` 是每次运行的空 dict，是唯一跨决策存活的东西；不要依赖模块级全局（进程可能被复用）。
- 抛异常或返回非法候选会**静默退回默认排序**，分数看着正常但策略其实没生效。
  每次跑完 grep `runs/<id>/agent.log` 里的 `could not be imported` / `raised` / `not legal now`。
- 评分常数从 `snapshot["score_config"]` / `snapshot["scoring_contract"]` 读 —— 官方
  `decision_graph.py:199-201` 会把它们注入快照。**但墙钟不在快照里**：`initialize` 的
  `global_wallclock_seconds` 不会传给 `choose_action`，要用 `os.environ["SAC_WALLCLOCK_SECONDS"]`。
  硬编码 1000/140/0.65 会在隐藏场景改数时静默失效。
- 快照里**没有总夜数 / 总时隙数**（`cursor` 只给当前 `night_id`，`night_start.night` 只给今晚）。
  所以「按剩余夜数 pacing」这类规则**无法实现**；预算判断只能靠自己量的墙钟消耗比例。
- 规则有两代。先读 `snapshot.schema_version`（v3 = 正式：重复观测合法、可上报、有覆盖奖励；
  v2 = 练习：重复观测 `duplicate_tile` −100、上报 `unknown_action`）。见
  [ADR 0002](docs/decisions/0002-target-the-v3-rules-not-just-dev-reference.md)。

## 验证口径

```bash
python scripts/ao.py run --scenario demo-week --strategy <name>     # ~20 s，先过这个门
python scripts/ao.py run --scenario dev-reference --strategy <name> # ~10 min，P0 = 12,287.478365
python scripts/ao.py score --run runs/<id>                          # 独立复算
python scripts/ao.py results
```

声称「更好」之前必须满足 `docs/experiment-protocol.md` 的 5 条门（demo-week 不 regress、
dev-reference 提升且分项方向可解释、≥2 个自造 ≥90 夜场景同向、墙钟 900→7200 不崩、
`agent.log` 零 fallback）。造场景：

```bash
python harness/make_scenario.py --out harness/scenarios/<name> --seed <n> --days 90
```

单看 dev-reference 一次分数**不构成证据**（单一固定 seed）。把结论写进
`submissions/LEDGER.md`，不要只留在对话里。

## 已知的直觉陷阱

- **`choose_action` 每场只被问 ~50–91 次，不是每个时隙一次。** `_finalize` 在没有「拍得完」的候选时
  直接返回 wait，根本不调用策略（dev-reference：7,943 时隙 / 91 次咨询）。所以问题是
  **「把这几十个名额分给谁」**，不是「每个时隙干什么」。写规则前先想这条。
- **等待不花钱**：实测 `wait_seconds.explicit == wait_seconds.unavailable`，`avoidable_wait`
  从未计费。花掉的是咨询名额本身。
- 「时间过剩、覆盖与罚分已打满」**只是 180 夜 dev-reference 的局部事实**：30 夜的 `mine-s7` 上
  同一个 greedy 只完成 52/64、吃 700 分 `flexible_shortfall`（R04 整区 0 块），终止原因仍是
  `survey_complete` —— 窗口轮不到，不是墙钟到点。**但那 700 分抢不到**：`quota-floor` 实测
  mine-s7 −1.77 / demo-week +24.64，块数与罚分都没变，因为缺口分区只在 50 次咨询里的 **7 次**
  上过板。别再加「优先补配额」类规则 —— `terminal_penalty_avoidance` 已在平台的
  `estimated_total_gain` 里，插队等于同一笔钱算两遍。
- 「天况不好就等」实测 **−1,700**（官方）。正确形态是带截止时间的可选延迟，不是阈值停拍。
- `coverage_bonus` 与 `report_reward` 在 dev-reference 上**恒为 0 / 非法**，别对着它们调参。
- 候选的 `program` 已由质量自动定档，**别改**；填错反而丢加成。

## 环境

Windows / git-bash，Python 3.11.1（`python`，`python3` 指向 WindowsApps 存根，别用）。
不需要 GPU，不需要密钥即可跑确定性基线。`agent/.env` 一旦创建就**不得入库**。

## 风格

注释默认不写，只在「为什么不明显」处写一行（隐藏约束、反直觉的实测结论、规避官方 bug）。
不写「这段在干什么」。不为假想的未来需求做抽象 —— 三个相似分支好过一个早熟的抽象。
